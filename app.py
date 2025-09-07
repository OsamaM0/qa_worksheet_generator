
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId, json_util
from typing import List, Dict, Any, Union
import re
import html as html_stdlib
import uvicorn
from worksheet_generator import WorksheetService
import os
import tempfile
import copy
import logging
from datetime import datetime
from dotenv import load_dotenv
from s3_service import get_s3_service, upload_worksheet_files
from mindmap_service import get_mindmap_service

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB configuration from environment
MONGO_URI = os.getenv("MONGO_URI", "mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=admin&serverSelectionTimeoutMS=30000&connectTimeoutMS=30000")
DB_NAME = os.getenv("DB_NAME", "ai")

# optional: try to use BeautifulSoup for robust HTML stripping; fallback to regex
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False


def _id_list_from_maybe_array(arr):
    if not arr:
        return []
    out = []
    for v in arr:
        try:
            out.append(v if isinstance(v, ObjectId) else ObjectId(v))
        except Exception:
            pass
    return out


def parse_comma_ids(s: str) -> List[int]:
    if not s:
        return []
    items = re.findall(r"\d+", s)
    return [int(x) for x in items]


def _strip_html(text: Union[str, None], html_parsing: bool) -> str:
    """
    If html_parsing is True => keep text as-is (but unescape HTML entities).
    If False => remove HTML tags and return plain text.
    """
    if not text:
        return "" if text is None else text
    # always unescape entities
    text = html_stdlib.unescape(text)
    if html_parsing:
        return text
    # remove tags
    if _HAS_BS4:
        # BeautifulSoup handles malformed HTML better
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    else:
        # simple fallback: remove tags and collapse whitespace
        no_tags = re.sub(r"<[^>]+>", " ", text)
        # normalize whitespace
        return re.sub(r"\s+", " ", no_tags).strip()


def _oid_to_serializable(obj):
    """
    Recursively convert ObjectId -> str for JSON-serializable dicts/lists.
    Use when you want a plain JSON output without bson.json_util.
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _oid_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_oid_to_serializable(v) for v in obj]
    return obj


def create_worksheet_from_lesson(lesson_id: Union[int, str, ObjectId],
                                 mongo_uri: str = "mongodb://localhost:27017",
                                 db_name: str = "mydb",
                                 html_parsing: bool = True,
                                 output: str = "worksheet",   # "worksheet" or "question_bank"
                                 include_raw_meta: bool = False
                                 ) -> Dict[str, Any]:
    """
    Build worksheet or question_bank JSON for a given lesson _id (ObjectId) or lessonId.

    Parameters:
      - lesson_id: Can be ObjectId (_id), string representation of ObjectId, or numeric lessonId
      - html_parsing: True -> keep HTML/markup (but unescape entities).
                      False -> strip all HTML tags and return plain text.
      - output: "worksheet" -> include sidebar/header_config
                "question_bank" -> return minimal structure with questions only
      - include_raw_meta: If True, return the raw lesson/goals/activities in 'meta' (may contain ObjectId).
                         If False, meta will be pre-serialized (ObjectId -> str).
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]

    # Try to find lesson by _id first (ObjectId), then fallback to lessonId (numeric)
    lesson = None
    if isinstance(lesson_id, ObjectId):
        lesson = db.lessons.find_one({"_id": lesson_id})
    elif isinstance(lesson_id, str):
        try:
            # Try as ObjectId string first
            obj_id = ObjectId(lesson_id)
            lesson = db.lessons.find_one({"_id": obj_id})
        except:
            # If not valid ObjectId, treat as string lessonId
            lesson = db.lessons.find_one({"lessonId": lesson_id})
    else:
        # Numeric lessonId (backward compatibility)
        lesson = db.lessons.find_one({"lessonId": lesson_id})
    
    if not lesson:
        client.close()
        raise ValueError(f"Lesson with ID={lesson_id} not found")

    lesson_map_goal_oids = _id_list_from_maybe_array(lesson.get("lessonMapGoals") or lesson.get("lessonMapGoals", []))
    goals_docs = []
    if lesson_map_goal_oids:
        goals_docs = list(db.lessonmappinggoals.find({"_id": {"$in": lesson_map_goal_oids}}))
    if not goals_docs:
        # Fallback: search by lesson _id instead of lessonId
        goals_docs = list(db.lessonmappinggoals.find({"lesson": lesson.get("_id")}))

    activities = list(db.lessonplanactivities.find({"lesson": lesson.get("_id")}))
    if not activities and lesson.get("lessonPlan"):
        activities = list(db.lessonplanactivities.find({"lessonPlan": lesson.get("lessonPlan")}))

    activity_goal_oids = []
    for act in activities:
        # Parse goals as ObjectIds instead of numeric IDs
        goals_str = act.get("goals", "")
        if goals_str:
            # Try to parse as comma-separated ObjectIds
            goal_parts = [g.strip() for g in str(goals_str).split(",") if g.strip()]
            for goal_part in goal_parts:
                try:
                    activity_goal_oids.append(ObjectId(goal_part))
                except:
                    # If not valid ObjectId, skip
                    pass
    
    # Collect goal ObjectIds from goals_docs
    goal_oids = [g.get("_id") for g in goals_docs if g.get("_id")]
    goal_oids = list(set(goal_oids + activity_goal_oids))

    q_filters = []
    # Search questions by lesson _id instead of lessonId
    q_filters.append({"lesson": lesson.get("_id")})
    if goal_oids:
        # Search questions by goal ObjectIds instead of goalId
        q_filters.append({"goal": {"$in": goal_oids}})
    if lesson.get("lessonPlan"):
        q_filters.append({"lessonPlan": lesson.get("lessonPlan")})
    question_query = {"$or": q_filters}

    questions = list(db.questions.find(question_query))

    semester = db.semesters.find_one({"_id": lesson.get("semester")}) if lesson.get("semester") else None
    level = db.levels.find_one({"_id": lesson.get("level")}) if lesson.get("level") else None
    subject = db.subjects.find_one({"_id": lesson.get("subject")}) if lesson.get("subject") else None
    stage = db.stages.find_one({"_id": lesson.get("stage")}) if lesson.get("stage") else None

    def question_to_choice_block(qdoc):
        qt = (qdoc.get("questionTypeName") or "").lower()
        title = _strip_html(qdoc.get("title"), html_parsing)
        if "صواب" in (qdoc.get("questionTypeName") or "") or "true" in qt:
            # True/False
            choices = [_strip_html(a.get("title"), html_parsing) for a in qdoc.get("questionAnswers", [])]
            answer_key = None
            for i, a in enumerate(qdoc.get("questionAnswers", [])):
                if a.get("isTrue"):
                    answer_key = i
            return {
                "question": title,
                "choices": choices,
                "answer_key": answer_key
            }
        else:
            if qdoc.get("questionAnswers"):
                choices = [_strip_html(a.get("title"), html_parsing) for a in qdoc.get("questionAnswers", [])]
                answer_key = next((i for i, a in enumerate(qdoc.get("questionAnswers", [])) if a.get("isTrue")), None)
                return {
                    "question": title,
                    "choices": choices,
                    "answer_key": answer_key
                }
            else:
                return {
                    "question": title,
                    "answer": _strip_html(qdoc.get("hint", ""), html_parsing)
                }

    multiple_choice_qs = []
    essay_qs = []
    for q in questions:
        mapped = question_to_choice_block(q)
        if "choices" in mapped:
            multiple_choice_qs.append(mapped)
        else:
            essay_qs.append(mapped)

    # base result for worksheet (full)
    worksheet_json = {
        "title": _strip_html(f"{lesson.get('title')}", html_parsing),
        "multiple_choice": {
            "header": _strip_html(": اختر الإجابة الصحيحة", html_parsing),
            "questions": multiple_choice_qs
        },
        "essay": {
            "header": _strip_html(": أجب عن الأسئلة التالية", html_parsing),
            "questions": essay_qs
        }
    }
    worksheet_json["header_config"] = {
            "subject_memo": _strip_html(subject.get("title"), html_parsing) if subject else None,
            "worksheet_number": _strip_html("بنك أسئلة 1", html_parsing),
            "name_label": _strip_html(" :الاسم", html_parsing),
            "class_label": _strip_html(" :الصف", html_parsing),
            "semester": _strip_html(semester.get("title"), html_parsing) if semester else None,
            "grade": _strip_html(level.get("title"), html_parsing) if level else None
        }
    
    worksheet_json["meta"] = {
            "lesson": lesson,
            "goals": goals_docs,
            "activities": activities,
            "raw_question_count": len(questions)
        }
    if output == "worksheet":
        worksheet_json["sidebar"] = {
                "before_lesson": _strip_html(lesson.get("title"), html_parsing),
                "goal": [_strip_html(g.get("title"), html_parsing) for g in goals_docs],
                "application": [],   # enrich if needed
                "level": ["ممتاز", "متوسط", "ضعيف"] if level else [],
                "notice": ""
            }
        
        worksheet_json["header_config"]["worksheet_number"] = "ورقة عمل 1"
        worksheet_json["title"] = "ورقة عمل - " + worksheet_json["title"]
    else:
        worksheet_json["title"] = "بنك أسئلة - " + worksheet_json["title"]

    # If user requested a lean question_bank, provide a compact structure
    if output == "question_bank":
        qb = {
            "title": _strip_html(lesson.get("title"), html_parsing),
            "questions": multiple_choice_qs + essay_qs,
            "header_config": worksheet_json["header_config"],
            "meta": worksheet_json["meta"]
        }
        final = qb
    else:
        final = worksheet_json

    # optionally convert ObjectId to strings for safe json.dumps consumers
    if not include_raw_meta:
        final_copy = _oid_to_serializable(final)
    else:
        final_copy = final

    client.close()
    return final_copy


def create_worksheet_from_ai_db(document_uuid: str,
                               mongo_uri: str = "mongodb://localhost:27017",
                               db_name: str = "ai",
                               html_parsing: bool = True,
                               output: str = "worksheet",   # "worksheet" or "question_bank"
                               include_raw_meta: bool = False
                               ) -> Dict[str, Any]:
    """
    Build worksheet or question_bank JSON from AI database structure.
    
    Parameters:
      - document_uuid: The document UUID to find in both questions and worksheets collections
      - html_parsing: True -> keep HTML/markup (but unescape entities).
                      False -> strip all HTML tags and return plain text.
      - output: "worksheet" -> include sidebar/header_config
                "question_bank" -> return minimal structure with questions only
      - include_raw_meta: If True, return the raw data in 'meta' (may contain ObjectId).
                         If False, meta will be pre-serialized (ObjectId -> str).
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]

    # Find questions document by document_uuid
    questions_doc = db.questions.find_one({"document_uuid": document_uuid})
    if not questions_doc:
        client.close()
        raise ValueError(f"Questions document with UUID={document_uuid} not found")

    # Find worksheet document by document_uuid
    worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
    if not worksheet_doc:
        client.close()
        raise ValueError(f"Worksheet document with UUID={document_uuid} not found")

    # Extract questions from the new format
    questions_data = questions_doc.get("questions", {})
    multiple_choice_qs = []
    true_false_qs = []
    short_answer_qs = []
    complete_qs = []

    # Process multiple choice questions
    for q in questions_data.get("multiple_choice", []):
        processed_q = {
            "question": _strip_html(q.get("question", ""), html_parsing),
            "choices": [_strip_html(choice, html_parsing) for choice in q.get("choices", [])],
            "answer_key": q.get("answer_key"),
            "type": "multiple_choice"
        }
        multiple_choice_qs.append(processed_q)

    # Process true/false questions
    for q in questions_data.get("true_false", []):
        processed_q = {
            "question": _strip_html(q.get("question", ""), html_parsing),
            "choices": ["صحيح", "خطأ"],  # Standard True/False choices in Arabic
            "answer_key": q.get("answer_key"),
            "type": "true_false"
        }
        true_false_qs.append(processed_q)

    # Process short answer questions
    for q in questions_data.get("short_answer", []):
        processed_q = {
            "question": _strip_html(q.get("question", ""), html_parsing),
            "answer": _strip_html(q.get("answer", ""), html_parsing),
            "type": "short_answer"
        }
        short_answer_qs.append(processed_q)

    # Process complete questions (fill in the blank)
    for q in questions_data.get("complete", []):
        processed_q = {
            "question": _strip_html(q.get("question", ""), html_parsing),
            "answer": _strip_html(q.get("answer", ""), html_parsing),
            "type": "complete"
        }
        complete_qs.append(processed_q)

    # Extract worksheet data
    worksheet_data = worksheet_doc.get("worksheet", {})
    goals = worksheet_data.get("goals", [])
    applications = worksheet_data.get("applications", [])
    vocabulary = worksheet_data.get("vocabulary", [])
    teacher_guidelines = worksheet_data.get("teacher_guidelines", [])

    # Get filename for title
    filename = worksheet_doc.get("filename", "")
    
    # Combine all questions for the questions section
    all_multiple_choice = multiple_choice_qs + true_false_qs
    all_essay = short_answer_qs + complete_qs

    # Build the worksheet JSON structure
    worksheet_json = {
        "title": _strip_html(filename, html_parsing),
        "multiple_choice": {
            "header": _strip_html(": اختر الإجابة الصحيحة", html_parsing),
            "questions": all_multiple_choice
        },
        "essay": {
            "header": _strip_html(": أجب عن الأسئلة التالية", html_parsing),
            "questions": all_essay
        },
        "header_config": {
            "subject_memo": "",  # Can be extracted from metadata if available
            "worksheet_number": _strip_html("ورقة عمل 1", html_parsing),
            "name_label": _strip_html(" :الاسم", html_parsing),
            "class_label": _strip_html(" :الصف", html_parsing),
            "semester": "",  # Can be extracted from metadata if available
            "grade": ""  # Can be extracted from metadata if available
        },
        "meta": {
            "questions_doc": questions_doc,
            "worksheet_doc": worksheet_doc,
            "total_questions": len(all_multiple_choice) + len(all_essay),
            "goals": goals,
            "applications": applications,
            "vocabulary": vocabulary,
            "teacher_guidelines": teacher_guidelines
        }
    }

    if output == "worksheet":
        worksheet_json["sidebar"] = {
            "before_lesson": _strip_html(filename, html_parsing),
            "goal": [_strip_html(goal, html_parsing) for goal in goals],
            "application": [_strip_html(app, html_parsing) for app in applications],
            "level": ["ممتاز", "متوسط", "ضعيف"],  # Standard levels
            "notice": ""
        }
        worksheet_json["vocabulary"] = [
            {
                "term": _strip_html(v.get("term", ""), html_parsing),
                "definition": _strip_html(v.get("definition", ""), html_parsing)
            }
            for v in vocabulary
        ]
        worksheet_json["teacher_guidelines"] = [
            _strip_html(guideline, html_parsing) for guideline in teacher_guidelines
        ]
        # Add applications as a top-level field for easy access
        worksheet_json["applications"] = [
            _strip_html(app, html_parsing) for app in applications
        ]
        
        worksheet_json["header_config"]["worksheet_number"] = "ورقة عمل 1"
        worksheet_json["title"] = "ورقة عمل - " + worksheet_json["title"]
    else:
        # Question bank format
        worksheet_json["title"] = "بنك أسئلة - " + worksheet_json["title"]

    # If user requested a lean question_bank, provide a compact structure
    if output == "question_bank":
        qb = {
            "title": _strip_html(filename, html_parsing),
            "questions": all_multiple_choice + all_essay,
            "header_config": worksheet_json["header_config"],
            "meta": worksheet_json["meta"]
        }
        final = qb
    else:
        final = worksheet_json

    # optionally convert ObjectId to strings for safe json.dumps consumers
    if not include_raw_meta:
        final_copy = _oid_to_serializable(final)
    else:
        final_copy = final

    client.close()
    return final_copy


def create_mindmap_from_ai_db(document_uuid: str,
                             mongo_uri: str = "mongodb://localhost:27017",
                             db_name: str = "ai",
                             html_parsing: bool = True,
                             include_raw_meta: bool = False
                             ) -> Dict[str, Any]:
    """
    Extract mindmap data from AI database structure.
    
    Parameters:
      - document_uuid: The document UUID to find in mindmaps collection
      - html_parsing: True -> keep HTML/markup (but unescape entities).
                      False -> strip all HTML tags and return plain text.
      - include_raw_meta: If True, return the raw data in 'meta' (may contain ObjectId).
                         If False, meta will be pre-serialized (ObjectId -> str).
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]

    # Find mindmap document by document_uuid
    mindmap_doc = db.mindmaps.find_one({"document_uuid": document_uuid})
    if not mindmap_doc:
        client.close()
        raise ValueError(f"Mindmap document with UUID={document_uuid} not found")

    # Extract mindmap data
    mindmap_data = mindmap_doc.get("mindmap", {})
    filename = mindmap_doc.get("filename", "")
    
    # Build the mindmap JSON structure
    mindmap_json = {
        "title": _strip_html(filename, html_parsing),
        "mindmap": mindmap_data,
        "meta": {
            "mindmap_doc": mindmap_doc,
            "filename": filename,
            "node_count": len(mindmap_data.get("nodeDataArray", [])),
            "document_uuid": document_uuid
        }
    }

    # optionally convert ObjectId to strings for safe json.dumps consumers
    if not include_raw_meta:
        final_copy = _oid_to_serializable(mindmap_json)
    else:
        final_copy = mindmap_json

    client.close()
    return final_copy


class PDFConverter:
    """Convert DOCX to PDF with Arabic support and logo watermark"""
    
    def __init__(self, logo_path: str = None):
        self.logo_path = logo_path or "logo.png"
        self._print_environment_info()
    
    def _print_environment_info(self):
        """Print environment information for debugging"""
        import platform
        import os
        print(f"=== PDF Converter Environment Info ===")
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python version: {platform.python_version()}")
        print(f"Working directory: {os.getcwd()}")
        
        # Check for PDF conversion tools
        tools_status = []
        
        # Check LibreOffice/soffice
        try:
            import subprocess
            result = subprocess.run(['libreoffice', '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                tools_status.append("✓ LibreOffice available")
            else:
                tools_status.append("✗ LibreOffice not found")
        except:
            tools_status.append("✗ LibreOffice not found")
        
        # Check unoconv
        try:
            result = subprocess.run(['unoconv', '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                tools_status.append("✓ unoconv available")
            else:
                tools_status.append("✗ unoconv not found")
        except:
            tools_status.append("✗ unoconv not found")
        
        # Check docx2pdf
        try:
            import docx2pdf
            tools_status.append("✓ docx2pdf library available")
        except ImportError:
            tools_status.append("✗ docx2pdf library not available")
        
        # Check comtypes (Windows)
        if platform.system() == "Windows":
            try:
                import comtypes
                tools_status.append("✓ comtypes available (Windows)")
            except ImportError:
                tools_status.append("✗ comtypes not available")
        
        for status in tools_status:
            print(status)
        print("==========================================")
    
    def convert_docx_to_pdf(self, docx_path: str, output_path: str) -> bool:
        """Convert DOCX file to PDF with logo watermark"""
        try:
            # Try different methods for DOCX to PDF conversion
            # Order optimized for server environments
            methods = [
                self._convert_with_unoconv,           # Best for Linux servers
                self._convert_with_libreoffice,       # Backup LibreOffice method
                self._convert_with_python_docx2pdf,   # Windows/local dev
                self._convert_with_comtypes,          # Windows only
                self._fallback_to_copy                # Last resort
            ]
            
            conversion_successful = False
            for method in methods:
                try:
                    print(f"Trying PDF conversion method: {method.__name__}")
                    if method(docx_path, output_path):
                        print(f"PDF conversion successful with: {method.__name__}")
                        conversion_successful = True
                        break
                except Exception as e:
                    print(f"Method {method.__name__} failed: {e}")
                    continue
            
            if conversion_successful:
                # Add watermark if conversion was successful
                try:
                    self._add_watermark_to_pdf(output_path)
                    print("Watermark added successfully")
                except Exception as e:
                    print(f"Watermark failed, but PDF was created: {e}")
                return True
            else:
                print("All PDF conversion methods failed")
                return False
                
        except Exception as e:
            print(f"PDF conversion error: {e}")
            return False
    
    def _convert_with_unoconv(self, docx_path: str, output_path: str) -> bool:
        """Try converting using unoconv (best for Linux servers)"""
        try:
            import subprocess
            import os
            
            # Check if unoconv is available
            try:
                subprocess.run(['unoconv', '--version'], capture_output=True, check=True, timeout=10)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                print("unoconv not available")
                return False
            
            # Get the output directory and filename
            output_dir = os.path.dirname(output_path)
            
            # Convert using unoconv
            cmd = [
                'unoconv',
                '-f', 'pdf',           # Format: PDF
                '-o', output_path,     # Output file
                docx_path              # Input file
            ]
            
            print(f"Running unoconv command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(output_path):
                print("unoconv conversion successful")
                return True
            else:
                print(f"unoconv failed with return code {result.returncode}")
                if result.stderr:
                    print(f"unoconv stderr: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"unoconv conversion failed: {e}")
            return False
    
    def _convert_with_python_docx2pdf(self, docx_path: str, output_path: str) -> bool:
        """Try converting using python-docx2pdf library"""
        try:
            from docx2pdf import convert
            convert(docx_path, output_path)
            return os.path.exists(output_path)
        except ImportError:
            print("docx2pdf library not available")
            return False
        except Exception as e:
            print(f"docx2pdf conversion failed: {e}")
            return False
    
    def _convert_with_comtypes(self, docx_path: str, output_path: str) -> bool:
        """Try converting using comtypes (Windows only)"""
        try:
            import comtypes.client
            import pythoncom
            
            pythoncom.CoInitialize()
            word = comtypes.client.CreateObject('Word.Application')
            word.Visible = False
            
            doc = word.Documents.Open(docx_path)
            doc.SaveAs(output_path, FileFormat=17)  # 17 is PDF format
            doc.Close()
            word.Quit()
            pythoncom.CoUninitialize()
            
            return os.path.exists(output_path)
        except ImportError:
            print("comtypes library not available")
            return False
        except Exception as e:
            print(f"comtypes conversion failed: {e}")
            return False
    
    def _convert_with_libreoffice(self, docx_path: str, output_path: str) -> bool:
        """Try converting using LibreOffice command line (improved version)"""
        try:
            import subprocess
            import os
            import time
            
            # Try common LibreOffice paths and commands
            libreoffice_commands = [
                ['libreoffice', '--headless', '--convert-to', 'pdf'],
                ['soffice', '--headless', '--convert-to', 'pdf'],
                ['/usr/bin/libreoffice', '--headless', '--convert-to', 'pdf'],
                ['/usr/bin/soffice', '--headless', '--convert-to', 'pdf'],
                ['C:\\Program Files\\LibreOffice\\program\\soffice.exe', '--headless', '--convert-to', 'pdf'],
                ['C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe', '--headless', '--convert-to', 'pdf']
            ]
            
            output_dir = os.path.dirname(output_path)
            
            for base_cmd in libreoffice_commands:
                try:
                    # Test if command exists
                    test_cmd = [base_cmd[0], '--version']
                    test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
                    if test_result.returncode != 0:
                        continue
                    
                    # Build full command
                    cmd = base_cmd + ['--outdir', output_dir, docx_path]
                    
                    print(f"Trying LibreOffice command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    
                    if result.returncode == 0:
                        # LibreOffice creates PDF with same base name as DOCX
                        base_name = os.path.splitext(os.path.basename(docx_path))[0]
                        generated_pdf = os.path.join(output_dir, f"{base_name}.pdf")
                        
                        # Wait a moment for file to be written
                        time.sleep(1)
                        
                        if os.path.exists(generated_pdf):
                            if generated_pdf != output_path:
                                if os.path.exists(output_path):
                                    os.remove(output_path)
                                os.rename(generated_pdf, output_path)
                            print("LibreOffice conversion successful")
                            return True
                    else:
                        print(f"LibreOffice failed with return code {result.returncode}")
                        if result.stderr:
                            print(f"LibreOffice stderr: {result.stderr}")
                        
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    print(f"LibreOffice command failed: {e}")
                    continue
            
            print("All LibreOffice commands failed")
            return False
            
        except Exception as e:
            print(f"LibreOffice conversion failed: {e}")
            return False
    
    def _fallback_to_copy(self, docx_path: str, output_path: str) -> bool:
        """Fallback: copy DOCX as 'PDF' (not a real conversion) - DO NOT USE for production"""
        try:
            import shutil
            # Create a .docx copy instead of pretending it's a PDF
            docx_copy_path = output_path.replace('.pdf', '_fallback.docx')
            shutil.copy2(docx_path, docx_copy_path)
            print(f"FALLBACK: Could not convert to PDF, copied DOCX file to {docx_copy_path}")
            return False  # Return False since it's not a real PDF conversion
        except Exception as e:
            print(f"Fallback copy failed: {e}")
            return False
    
    def _add_watermark_to_pdf(self, pdf_path: str) -> bool:
        """Add logo watermark to PDF"""
        try:
            # Try to add watermark using PyPDF2/PyPDF4 or reportlab
            if self._add_watermark_with_reportlab(pdf_path):
                return True
            elif self._add_watermark_with_pypdf(pdf_path):
                return True
            else:
                print("Could not add watermark - no suitable library available")
                return False
        except Exception as e:
            print(f"Watermark addition failed: {e}")
            return False
    
    def _add_watermark_with_reportlab(self, pdf_path: str) -> bool:
        """Add watermark using ReportLab"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import tempfile
            
            if not os.path.exists(self.logo_path):
                print(f"Logo file not found: {self.logo_path}")
                return False
            
            # Create watermark PDF
            watermark_path = os.path.join(tempfile.gettempdir(), "watermark.pdf")
            c = canvas.Canvas(watermark_path, pagesize=A4)
            
            # Add logo as watermark (transparent, in background)
            img = ImageReader(self.logo_path)
            img_width, img_height = img.getSize()
            
            # Scale logo to fit page while maintaining aspect ratio
            page_width, page_height = A4
            scale = min(page_width / img_width, page_height / img_height) * 0.5  # 50% of page size
            new_width = img_width * scale
            new_height = img_height * scale
            
            # Center the logo
            x = (page_width - new_width) / 2
            y = (page_height - new_height) / 2
            
            # Draw with low opacity
            c.setFillAlpha(0.1)  # Very transparent
            c.drawImage(img, x, y, width=new_width, height=new_height, mask='auto')
            c.save()
            
            # Merge watermark with original PDF
            try:
                from PyPDF2 import PdfReader, PdfWriter
                return self._merge_pdfs_pypdf2(pdf_path, watermark_path)
            except ImportError:
                try:
                    from PyPDF4 import PdfFileReader, PdfFileWriter
                    return self._merge_pdfs_pypdf4(pdf_path, watermark_path)
                except ImportError:
                    print("No PDF merging library available")
                    return False
            
        except ImportError:
            print("ReportLab not available for watermarking")
            return False
        except Exception as e:
            print(f"ReportLab watermark failed: {e}")
            return False
    
    def _add_watermark_with_pypdf(self, pdf_path: str) -> bool:
        """Add simple text watermark using PyPDF libraries"""
        try:
            # This is a simplified approach if ReportLab watermarking fails
            print("Simple watermark approach - logo watermark not implemented yet")
            return True  # Return True to indicate PDF exists, even without watermark
        except Exception as e:
            print(f"PyPDF watermark failed: {e}")
            return False
    
    def _merge_pdfs_pypdf2(self, original_pdf: str, watermark_pdf: str) -> bool:
        """Merge PDFs using PyPDF2"""
        try:
            from PyPDF2 import PdfReader, PdfWriter
            
            original = PdfReader(original_pdf)
            watermark = PdfReader(watermark_pdf)
            writer = PdfWriter()
            
            watermark_page = watermark.pages[0]
            
            for page in original.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)
            
            with open(original_pdf, 'wb') as output_file:
                writer.write(output_file)
            
            # Clean up watermark file
            os.remove(watermark_pdf)
            return True
            
        except Exception as e:
            print(f"PyPDF2 merge failed: {e}")
            return False
    
    def _merge_pdfs_pypdf4(self, original_pdf: str, watermark_pdf: str) -> bool:
        """Merge PDFs using PyPDF4"""
        try:
            from PyPDF4 import PdfFileReader, PdfFileWriter
            
            original = PdfFileReader(original_pdf)
            watermark = PdfFileReader(watermark_pdf)
            writer = PdfFileWriter()
            
            watermark_page = watermark.getPage(0)
            
            for i in range(original.getNumPages()):
                page = original.getPage(i)
                page.mergePage(watermark_page)
                writer.addPage(page)
            
            with open(original_pdf, 'wb') as output_file:
                writer.write(output_file)
            
            # Clean up watermark file
            os.remove(watermark_pdf)
            return True
            
        except Exception as e:
            print(f"PyPDF4 merge failed: {e}")
            return False


# --- FastAPI App ---
app = FastAPI(
    title="QA Worksheet Generator API",
    description="API for generating worksheets, questions, and mindmaps with S3 storage",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_worksheet_with_custom_counts(document_uuid: str, mongo_uri: str, db_name: str, 
                                       multiple_choice_count: int, true_false_count: int, 
                                       short_answer_count: int, complete_count: int,
                                       include_solutions: bool = False, 
                                       generate_pdf: bool = False) -> Dict[str, Any]:
    """
    Generate worksheet DOCX with custom question counts and solution options.
    Optionally convert to PDF if generate_pdf is True.
    """
    try:
        # Get worksheet data from AI database
        data = create_worksheet_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=mongo_uri,
            db_name=db_name,
            html_parsing=False,
            output="worksheet",
            include_raw_meta=False
        )

        # Apply question type-specific limits
        data = _limit_questions_by_type(
            data, 
            multiple_choice_count=multiple_choice_count,
            true_false_count=true_false_count,
            short_answer_count=short_answer_count,
            complete_count=complete_count
        )

        # Get document title for file naming
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        if not worksheet_doc:
            client.close()
            return {"status": "error", "message": f"Worksheet document with UUID {document_uuid} not found"}
        
        client.close()
        document_title = _get_document_title(worksheet_doc, False)

        # Clean document title for filename
        document_title_clean = re.sub(r'[<>:"/\\|?*]', '_', document_title)
        solution_suffix = "_with_solutions" if include_solutions else "_no_solutions"
        base_filename = f"{document_title_clean}_ورقة_عمل{solution_suffix}"
        
        # Create copy for solution handling
        data_final = copy.deepcopy(data)
        
        # Remove answers if no solutions requested
        if not include_solutions:
            def _remove_answers(d):
                if isinstance(d, dict):
                    for k in list(d.keys()):
                        if k in ("answer_key", "answer"):
                            d[k] = None
                        else:
                            _remove_answers(d[k])
                elif isinstance(d, list):
                    for item in d:
                        _remove_answers(item)
            _remove_answers(data_final)

        # Generate DOCX
        service = WorksheetService()
        docx_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.docx")
        docx_result = service.create_worksheet(data_final, docx_path)
        
        if docx_result["status"] != "success":
            return {"status": "error", "message": f"DOCX generation failed: {docx_result['message']}"}

        # Return DOCX by default
        result = {
            "status": "success",
            "file_path": docx_path,
            "filename": f"{base_filename}.docx",
            "format": "docx"
        }

        # Convert to PDF only if requested
        if generate_pdf:
            pdf_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.pdf")
            pdf_converter = PDFConverter("logo.png")
            
            if pdf_converter.convert_docx_to_pdf(docx_path, pdf_path):
                # Clean up DOCX since we're returning PDF
                try:
                    os.remove(docx_path)
                except:
                    pass
                
                result = {
                    "status": "success",
                    "file_path": pdf_path,
                    "filename": f"{base_filename}.pdf",
                    "format": "pdf"
                }
            else:
                # If PDF conversion fails, return DOCX
                result["pdf_conversion_failed"] = True
                result["message"] = "DOCX generated successfully, but PDF conversion failed"
        
        return result
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_question_bank_with_custom_counts(document_uuid: str, mongo_uri: str, db_name: str, 
                                            multiple_choice_count: int, true_false_count: int, 
                                            short_answer_count: int, complete_count: int,
                                            include_solutions: bool = False,
                                            generate_pdf: bool = False) -> Dict[str, Any]:
    """
    Generate question bank DOCX with custom question counts and solution options.
    Optionally convert to PDF if generate_pdf is True.
    """
    try:
        # Get question bank data from AI database
        data = create_worksheet_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=mongo_uri,
            db_name=db_name,
            html_parsing=False,
            output="question_bank",
            include_raw_meta=False
        )

        # Apply question type-specific limits
        data = _limit_questions_by_type(
            data, 
            multiple_choice_count=multiple_choice_count,
            true_false_count=true_false_count,
            short_answer_count=short_answer_count,
            complete_count=complete_count
        )

        # Get document title for file naming
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        if not worksheet_doc:
            client.close()
            return {"status": "error", "message": f"Document with UUID {document_uuid} not found"}
        
        client.close()
        document_title = _get_document_title(worksheet_doc, False)

        # Clean document title for filename
        document_title_clean = re.sub(r'[<>:"/\\|?*]', '_', document_title)
        solution_suffix = "_with_solutions" if include_solutions else "_no_solutions"
        base_filename = f"{document_title_clean}_بنك_أسئله{solution_suffix}"
        
        # Create copy for solution handling
        data_final = copy.deepcopy(data)
        
        # Remove answers if no solutions requested
        if not include_solutions:
            def _remove_answers(d):
                if isinstance(d, dict):
                    for k in list(d.keys()):
                        if k in ("answer_key", "answer"):
                            d[k] = None
                        else:
                            _remove_answers(d[k])
                elif isinstance(d, list):
                    for item in d:
                        _remove_answers(item)
            _remove_answers(data_final)

        # Generate DOCX
        service = WorksheetService()
        docx_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.docx")
        docx_result = service.create_worksheet(data_final, docx_path)
        
        if docx_result["status"] != "success":
            return {"status": "error", "message": f"DOCX generation failed: {docx_result['message']}"}

        # Return DOCX by default
        result = {
            "status": "success",
            "file_path": docx_path,
            "filename": f"{base_filename}.docx",
            "format": "docx"
        }

        # Convert to PDF only if requested
        if generate_pdf:
            pdf_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.pdf")
            pdf_converter = PDFConverter("logo.png")
            
            if pdf_converter.convert_docx_to_pdf(docx_path, pdf_path):
                # Clean up DOCX since we're returning PDF
                try:
                    os.remove(docx_path)
                except:
                    pass
                
                result = {
                    "status": "success",
                    "file_path": pdf_path,
                    "filename": f"{base_filename}.pdf",
                    "format": "pdf"
                }
            else:
                # If PDF conversion fails, return DOCX
                result["pdf_conversion_failed"] = True
                result["message"] = "DOCX generated successfully, but PDF conversion failed"
        
        return result
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_worksheet_pdf(document_uuid: str, mongo_uri: str, db_name: str) -> Dict[str, Any]:
    """
    Generate only worksheet PDF for the unified endpoint
    """
    try:
        # Get worksheet data from AI database
        data = create_worksheet_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=mongo_uri,
            db_name=db_name,
            html_parsing=False,
            output="worksheet",
            include_raw_meta=False
        )

        # Get document title for file naming
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        if not worksheet_doc:
            client.close()
            return {"status": "error", "message": f"Worksheet document with UUID {document_uuid} not found"}
        
        client.close()
        document_title = _get_document_title(worksheet_doc, False)

        # Clean document title for filename
        document_title_clean = re.sub(r'[<>:"/\\|?*]', '_', document_title)
        base_filename = f"{document_title_clean}_ورقة_عمل"
        
        # Create version without solutions
        data_no_solutions = copy.deepcopy(data)
        def _remove_answers(d):
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k in ("answer_key", "answer"):
                        d[k] = None
                    else:
                        _remove_answers(d[k])
            elif isinstance(d, list):
                for item in d:
                    _remove_answers(item)
        _remove_answers(data_no_solutions)

        # Generate DOCX first
        service = WorksheetService()
        docx_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.docx")
        docx_result = service.create_worksheet(data_no_solutions, docx_path)
        
        if docx_result["status"] != "success":
            return {"status": "error", "message": f"DOCX generation failed: {docx_result['message']}"}

        # Convert to PDF
        pdf_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.pdf")
        pdf_converter = PDFConverter("logo.png")
        
        if pdf_converter.convert_docx_to_pdf(docx_path, pdf_path):
            # Clean up DOCX
            try:
                os.remove(docx_path)
            except:
                pass
            
            return {
                "status": "success",
                "file_path": pdf_path,
                "filename": f"{base_filename}.pdf"
            }
        else:
            return {"status": "error", "message": "DOCX to PDF conversion failed"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_question_bank_pdf(document_uuid: str, mongo_uri: str, db_name: str) -> Dict[str, Any]:
    """
    Generate only question bank PDF for the unified endpoint
    """
    try:
        # Get question bank data from AI database
        data = create_worksheet_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=mongo_uri,
            db_name=db_name,
            html_parsing=False,
            output="question_bank",
            include_raw_meta=False
        )

        # Get document title for file naming
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        if not worksheet_doc:
            client.close()
            return {"status": "error", "message": f"Document with UUID {document_uuid} not found"}
        
        client.close()
        document_title = _get_document_title(worksheet_doc, False)

        # Clean document title for filename
        document_title_clean = re.sub(r'[<>:"/\\|?*]', '_', document_title)
        base_filename = f"{document_title_clean}_بنك_أسئله"
        
        # Create version without solutions
        data_no_solutions = copy.deepcopy(data)
        def _remove_answers(d):
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k in ("answer_key", "answer"):
                        d[k] = None
                    else:
                        _remove_answers(d[k])
            elif isinstance(d, list):
                for item in d:
                    _remove_answers(item)
        _remove_answers(data_no_solutions)

        # Generate DOCX first
        service = WorksheetService()
        docx_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.docx")
        docx_result = service.create_worksheet(data_no_solutions, docx_path)
        
        if docx_result["status"] != "success":
            return {"status": "error", "message": f"DOCX generation failed: {docx_result['message']}"}

        # Convert to PDF
        pdf_path = os.path.join(tempfile.gettempdir(), f"{base_filename}.pdf")
        pdf_converter = PDFConverter("logo.png")
        
        if pdf_converter.convert_docx_to_pdf(docx_path, pdf_path):
            # Clean up DOCX
            try:
                os.remove(docx_path)
            except:
                pass
            
            return {
                "status": "success",
                "file_path": pdf_path,
                "filename": f"{base_filename}.pdf"
            }
        else:
            return {"status": "error", "message": "DOCX to PDF conversion failed"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _get_lesson_title(lesson_doc, html_parsing):
    return _strip_html(lesson_doc.get('title', 'lesson'), html_parsing)

def _get_document_title(worksheet_doc, html_parsing):
    return _strip_html(worksheet_doc.get('filename', 'document'), html_parsing)

def _limit_questions(data, num_questions):
    if not num_questions or num_questions <= 0:
        return data
    # Limit both multiple_choice and essay
    if 'multiple_choice' in data and 'questions' in data['multiple_choice']:
        data['multiple_choice']['questions'] = data['multiple_choice']['questions'][:num_questions]
    if 'essay' in data and 'questions' in data['essay']:
        data['essay']['questions'] = data['essay']['questions'][:num_questions]
    if 'questions' in data:
        data['questions'] = data['questions'][:num_questions]
    return data

def _limit_questions_by_type(data, multiple_choice_count=-1, true_false_count=-1, short_answer_count=-1, complete_count=-1):
    """
    Limit questions by specific types with individual controls.
    
    Parameters:
        -1: Include all questions of this type
         0: Include no questions of this type  
         N: Include exactly N questions of this type
    """
    
    # Handle multiple choice questions (includes both multiple_choice and true_false)
    if 'multiple_choice' in data and 'questions' in data['multiple_choice']:
        mc_questions = data['multiple_choice']['questions']
        
        # Separate multiple choice and true/false
        pure_mc = [q for q in mc_questions if q.get('type') == 'multiple_choice']
        true_false = [q for q in mc_questions if q.get('type') == 'true_false']
        other_mc = [q for q in mc_questions if q.get('type') not in ['multiple_choice', 'true_false']]
        
        final_mc_questions = []
        
        # Apply multiple choice limit
        if multiple_choice_count != 0:
            if multiple_choice_count == -1:
                final_mc_questions.extend(pure_mc)
            else:
                final_mc_questions.extend(pure_mc[:multiple_choice_count])
        
        # Apply true/false limit
        if true_false_count != 0:
            if true_false_count == -1:
                final_mc_questions.extend(true_false)
            else:
                final_mc_questions.extend(true_false[:true_false_count])
        
        # Add other unclassified questions
        final_mc_questions.extend(other_mc)
        
        data['multiple_choice']['questions'] = final_mc_questions
    
    # Handle essay questions (short answer + complete)
    if 'essay' in data and 'questions' in data['essay']:
        essay_questions = data['essay']['questions']
        
        # Separate by type
        short_answer_qs = [q for q in essay_questions if q.get('type') == 'short_answer']
        complete_qs = [q for q in essay_questions if q.get('type') == 'complete']
        other_qs = [q for q in essay_questions if q.get('type') not in ['short_answer', 'complete']]
        
        # Apply limits
        final_essay_questions = []
        
        if short_answer_count != 0:
            if short_answer_count == -1:
                final_essay_questions.extend(short_answer_qs)
            else:
                final_essay_questions.extend(short_answer_qs[:short_answer_count])
        
        if complete_count != 0:
            if complete_count == -1:
                final_essay_questions.extend(complete_qs)
            else:
                final_essay_questions.extend(complete_qs[:complete_count])
        
        # Add other questions that couldn't be classified
        final_essay_questions.extend(other_qs)
        
        data['essay']['questions'] = final_essay_questions
    
    return data

@app.get("/generate-worksheet/")
def generate_worksheet(
    document_uuid: str = Query(..., description="Document UUID from AI database"),
    output: str = Query("worksheet", description="worksheet or question_bank"),
    num_questions: int = Query(0, description="Number of questions to include (0 = all, legacy parameter)"),
    multiple_choice_count: int = Query(-1, description="Number of multiple choice questions (-1 = all, 0 = none, N = exact count)"),
    true_false_count: int = Query(-1, description="Number of true/false questions (-1 = all, 0 = none, N = exact count)"),
    short_answer_count: int = Query(-1, description="Number of short answer questions (-1 = all, 0 = none, N = exact count)"),
    complete_count: int = Query(-1, description="Number of complete/fill-in-blank questions (-1 = all, 0 = none, N = exact count)"),
    generate_pdf: bool = Query(True, description="Generate PDF files (default: True)"),
    html_parsing: bool = Query(False, description="Keep HTML markup (default: False)"),
    mongo_uri: str = Query(None, description="Override MongoDB URI (uses env MONGO_URI if not provided)"),
    db_name: str = Query(None, description="Override DB name (uses env DB_NAME if not provided)")
):
    """
    Generate worksheet/question bank for a document from AI database. Returns files: JSON, DOCX, and optionally PDF.
    Uses document_uuid to find data in questions and worksheets collections.
    """
    try:
        # Use environment variables as defaults
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME

        # Get worksheet/question bank data from AI database
        data = create_worksheet_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=effective_mongo_uri,
            db_name=effective_db_name,
            html_parsing=html_parsing,
            output=output,
            include_raw_meta=False
        )

        # Apply question type-specific limits
        data = _limit_questions_by_type(
            data, 
            multiple_choice_count=multiple_choice_count,
            true_false_count=true_false_count,
            short_answer_count=short_answer_count,
            complete_count=complete_count
        )

        # Legacy support: if num_questions is specified, use old limiting method
        if num_questions and num_questions > 0:
            data = _limit_questions(data, num_questions)

        # Get document title for file naming
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        # Find document in worksheets collection for title
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        if not worksheet_doc:
            client.close()
            return {"error": f"Worksheet document with UUID {document_uuid} not found"}
        
        client.close()
        document_title = _get_document_title(worksheet_doc, html_parsing) if worksheet_doc else f"document_{document_uuid}"

        # Clean document title for filename
        document_title_clean = re.sub(r'[<>:"/\\|?*]', '_', document_title)
        suffix = "_ورقة_عمل" if output == "worksheet" else "_بنك_أسئله"
        base_filename = f"{document_title_clean}{suffix}"        # Create copies for solutions and no solutions
        data_with_solutions = copy.deepcopy(data)
        data_no_solutions = copy.deepcopy(data)
        
        # Remove answers from no_solutions version
        def _remove_answers(d):
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k in ("answer_key", "answer"):
                        d[k] = None
                    else:
                        _remove_answers(d[k])
            elif isinstance(d, list):
                for item in d:
                    _remove_answers(item)
        _remove_answers(data_no_solutions)

        # Initialize result
        result = {
            "document_title": document_title,
            "base_filename": base_filename,
            "generate_pdf": generate_pdf,
            "files": {},
            "s3_uploads": {}
        }

        # Store local file paths for S3 upload
        local_files = {}

        # Generate JSON files
        try:
            json_no_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_no_solutions.json")
            with open(json_no_solutions, "w", encoding="utf-8") as f:
                f.write(json_util.dumps(data_no_solutions, ensure_ascii=False, indent=2))
            result["files"]["json_no_solutions"] = json_no_solutions
            local_files["json_no_solutions"] = json_no_solutions

            json_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.json")
            with open(json_with_solutions, "w", encoding="utf-8") as f:
                f.write(json_util.dumps(data_with_solutions, ensure_ascii=False, indent=2))
            result["files"]["json_with_solutions"] = json_with_solutions
            local_files["json_with_solutions"] = json_with_solutions
        except Exception as e:
            result["files"]["json_error"] = str(e)

        # Generate DOCX files using WorksheetService
        try:
            service = WorksheetService()
            
            docx_no_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_no_solutions.docx")
            docx_result_no_sol = service.create_worksheet(data_no_solutions, docx_no_solutions)
            if docx_result_no_sol["status"] == "success":
                result["files"]["docx_no_solutions"] = docx_no_solutions
                local_files["docx_no_solutions"] = docx_no_solutions
            else:
                result["files"]["docx_no_solutions_error"] = docx_result_no_sol["message"]

            docx_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.docx")
            docx_result_with_sol = service.create_worksheet(data_with_solutions, docx_with_solutions)
            if docx_result_with_sol["status"] == "success":
                result["files"]["docx_with_solutions"] = docx_with_solutions
                local_files["docx_with_solutions"] = docx_with_solutions
            else:
                result["files"]["docx_with_solutions_error"] = docx_result_with_sol["message"]
                
        except Exception as e:
            result["files"]["docx_error"] = str(e)

        # Generate PDF files only if requested
        if generate_pdf:
            try:
                pdf_converter = PDFConverter("logo.png")
                
                if "docx_no_solutions" in result["files"]:
                    pdf_no_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_no_solutions.pdf")
                    if pdf_converter.convert_docx_to_pdf(result["files"]["docx_no_solutions"], pdf_no_solutions):
                        result["files"]["pdf_no_solutions"] = pdf_no_solutions
                        local_files["pdf_no_solutions"] = pdf_no_solutions
                    else:
                        result["files"]["pdf_no_solutions_error"] = "DOCX to PDF conversion failed - check server PDF conversion tools (LibreOffice/unoconv)"

                if "docx_with_solutions" in result["files"]:
                    pdf_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.pdf")
                    if pdf_converter.convert_docx_to_pdf(result["files"]["docx_with_solutions"], pdf_with_solutions):
                        result["files"]["pdf_with_solutions"] = pdf_with_solutions
                        local_files["pdf_with_solutions"] = pdf_with_solutions
                    else:
                        result["files"]["pdf_with_solutions_error"] = "DOCX to PDF conversion failed - check server PDF conversion tools (LibreOffice/unoconv)"
                    
            except Exception as e:
                result["files"]["pdf_error"] = f"PDF conversion system error: {str(e)}. Check server configuration and PDF tools installation."
        else:
            result["files"]["pdf_skipped"] = "PDF generation disabled by user"

        # Upload files to S3
        if local_files:
            try:
                s3_upload_result = upload_worksheet_files(local_files, document_title)
                result["s3_uploads"] = s3_upload_result
                
                # Clean up local temporary files after successful upload
                if s3_upload_result.get("status") in ["success", "partial"]:
                    for file_path in local_files.values():
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as cleanup_error:
                            print(f"Warning: Could not clean up temporary file {file_path}: {cleanup_error}")
                
                # Update result with S3 URLs instead of local paths
                if "files" in s3_upload_result:
                    result["files"] = {}  # Clear local paths
                    for file_type, upload_info in s3_upload_result["files"].items():
                        result["files"][file_type] = upload_info["public_url"]
                        
            except Exception as e:
                result["s3_uploads"] = {"status": "error", "message": f"S3 upload failed: {str(e)}"}
                # Keep local files info if S3 upload fails
                print(f"S3 upload failed, keeping local files: {e}")

        return result

    except Exception as e:
        return {
            "error": str(e),
            "document_uuid": document_uuid,
            "output": output
        }


@app.get("/generate-worksheet-legacy/")
def generate_worksheet_legacy(
    lesson_id: str = Query(..., description="Lesson ID (ObjectId string or numeric lessonId) - Legacy format"),
    output: str = Query("worksheet", description="worksheet or question_bank"),
    num_questions: int = Query(0, description="Number of questions to include (0 = all)"),
    generate_pdf: bool = Query(True, description="Generate PDF files (default: True)"),
    html_parsing: bool = Query(False, description="Keep HTML markup (default: False)"),
    mongo_uri: str = Query(None, description="Override MongoDB URI (uses env MONGO_URI if not provided)"),
    db_name: str = Query(None, description="Override DB name (uses env DB_NAME if not provided)")
):
    """
    Legacy endpoint for generating worksheets from the old IEN database structure.
    This endpoint maintains backward compatibility with the old lesson-based approach.
    """
    try:
        # Use environment variables as defaults, but force to use IEN database for legacy
        legacy_mongo_uri = mongo_uri or "mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien"
        legacy_db_name = db_name or "ien"

        # Get worksheet/question bank data using the legacy function
        data = create_worksheet_from_lesson(
            lesson_id=lesson_id,
            mongo_uri=legacy_mongo_uri,
            db_name=legacy_db_name,
            html_parsing=html_parsing,
            output=output,
            include_raw_meta=False
        )

        # Limit number of questions if requested
        if num_questions and num_questions > 0:
            data = _limit_questions(data, num_questions)

        # Return minimal JSON response for legacy compatibility
        return {
            "status": "success",
            "data": data,
            "lesson_id": lesson_id,
            "output": output,
            "message": "Legacy worksheet generated successfully"
        }

    except Exception as e:
        return {
            "error": str(e),
            "lesson_id": lesson_id,
            "output": output,
            "message": "Legacy worksheet generation failed"
        }


@app.get("/search-documents/")
def search_documents(
    query: str = Query(..., description="Search query: document UUID, filename, or text fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Search for documents in the AI database by UUID, filename, or text fragment.
    Returns document information to help find the correct document_uuid for worksheet generation.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        search_filters = []
        
        # Try document UUID search
        search_filters.append({"document_uuid": query})
        
        # Try filename search
        search_filters.append({"filename": {"$regex": query, "$options": "i"}})
        
        # Build query
        if len(search_filters) > 1:
            final_query = {"$or": search_filters}
        elif len(search_filters) == 1:
            final_query = search_filters[0]
        else:
            final_query = {}
        
        # Search in both collections
        worksheets = list(db.worksheets.find(final_query).limit(limit))
        questions = list(db.questions.find(final_query).limit(limit))
        
        client.close()
        
        # Format results
        results = []
        
        # Add worksheet results
        for doc in worksheets:
            results.append({
                "_id": str(doc.get("_id")),
                "document_uuid": doc.get("document_uuid"),
                "filename": doc.get("filename"),
                "type": "worksheet",
                "goals_count": len(doc.get("goals", [])),
                "generated_at": doc.get("generated_at")
            })
        
        # Add question results (if not already included from worksheets)
        existing_uuids = {r["document_uuid"] for r in results}
        for doc in questions:
            if doc.get("document_uuid") not in existing_uuids:
                results.append({
                    "_id": str(doc.get("_id")),
                    "document_uuid": doc.get("document_uuid"),
                    "filename": doc.get("filename"),
                    "type": "questions",
                    "questions_count": sum(len(doc.get("questions", {}).get(qtype, [])) 
                                         for qtype in ["multiple_choice", "true_false", "short_answer", "complete"]),
                    "generated_at": doc.get("generated_at")
                })
        
        return {
            "query": query,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "query": query
        }


@app.get("/document-details/{document_uuid}")
def get_document_details(
    document_uuid: str,
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Get detailed information about a document by UUID from the AI database.
    Shows both worksheet and questions data.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        # Find documents by UUID
        worksheet_doc = db.worksheets.find_one({"document_uuid": document_uuid})
        questions_doc = db.questions.find_one({"document_uuid": document_uuid})
        
        if not worksheet_doc and not questions_doc:
            client.close()
            return {"error": f"Document with UUID {document_uuid} not found"}
        
        # Build details response
        details = {
            "document_uuid": document_uuid,
            "worksheet_data": _oid_to_serializable(worksheet_doc) if worksheet_doc else None,
            "questions_data": _oid_to_serializable(questions_doc) if questions_doc else None
        }
        
        client.close()
        return details
        
    except Exception as e:
        return {
            "error": str(e),
            "document_uuid": document_uuid
        }


@app.get("/pdf-status/")
def check_pdf_conversion_status():
    """
    Check the availability of PDF conversion tools on the server.
    Useful for debugging PDF conversion issues.
    """
    try:
        import subprocess
        import platform
        
        status = {
            "platform": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "pdf_conversion_tools": {},
            "recommendations": []
        }
        
        # Check LibreOffice
        try:
            result = subprocess.run(['libreoffice', '--version'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.decode().strip().split('\n')[0]
                status["pdf_conversion_tools"]["libreoffice"] = {
                    "available": True,
                    "version": version
                }
            else:
                status["pdf_conversion_tools"]["libreoffice"] = {
                    "available": False,
                    "error": "Command failed"
                }
        except Exception as e:
            status["pdf_conversion_tools"]["libreoffice"] = {
                "available": False,
                "error": str(e)
            }
        
        # Check unoconv
        try:
            result = subprocess.run(['unoconv', '--version'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.decode().strip().split('\n')[0]
                status["pdf_conversion_tools"]["unoconv"] = {
                    "available": True,
                    "version": version
                }
            else:
                status["pdf_conversion_tools"]["unoconv"] = {
                    "available": False,
                    "error": "Command failed"
                }
        except Exception as e:
            status["pdf_conversion_tools"]["unoconv"] = {
                "available": False,
                "error": str(e)
            }
        
        # Check docx2pdf
        try:
            import docx2pdf
            status["pdf_conversion_tools"]["docx2pdf"] = {
                "available": True,
                "note": "Python library available (requires Windows/Office)"
            }
        except ImportError:
            status["pdf_conversion_tools"]["docx2pdf"] = {
                "available": False,
                "error": "Python library not installed"
            }
        
        # Check comtypes (Windows only)
        if platform.system() == "Windows":
            try:
                import comtypes
                status["pdf_conversion_tools"]["comtypes"] = {
                    "available": True,
                    "note": "Windows COM library available"
                }
            except ImportError:
                status["pdf_conversion_tools"]["comtypes"] = {
                    "available": False,
                    "error": "Python library not installed"
                }
        
        # Generate recommendations
        has_working_tool = any(
            tool.get("available", False) 
            for tool in status["pdf_conversion_tools"].values()
        )
        
        if not has_working_tool:
            status["recommendations"].extend([
                "Install LibreOffice: apt-get install libreoffice libreoffice-writer",
                "Install unoconv: apt-get install unoconv",
                "Install additional fonts: apt-get install fonts-noto fonts-liberation"
            ])
        
        status["pdf_conversion_available"] = has_working_tool
        
        return status
        
    except Exception as e:
        return {
            "error": f"Failed to check PDF conversion status: {str(e)}",
            "pdf_conversion_available": False
        }


@app.get("/s3-status/")
def check_s3_status():
    """
    Check the availability and health of S3/R2 storage service.
    Useful for debugging S3 upload issues.
    """
    try:
        s3_service = get_s3_service()
        health_status = s3_service.health_check()
        
        # Add configuration info (without sensitive data)
        health_status["configuration"] = {
            "endpoint": s3_service.endpoint_url,
            "bucket": s3_service.bucket_name,
            "has_credentials": bool(s3_service.access_key_id and s3_service.secret_access_key)
        }
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": "service_initialization_failed",
            "message": str(e),
            "s3_available": False
        }


@app.get("/search-lessons/")
def search_lessons(
    query: str = Query(..., description="Search query: ObjectId, numeric lessonId, or title fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Search for lessons by ObjectId, lessonId, or title fragment.
    Returns lesson information to help find the correct lesson_id for worksheet generation.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        search_filters = []
        
        # Try ObjectId search
        try:
            obj_id = ObjectId(query)
            search_filters.append({"_id": obj_id})
        except:
            pass
        
        # Try numeric lessonId search
        try:
            numeric_id = int(query)
            search_filters.append({"lessonId": numeric_id})
        except:
            pass
        
        # Text search in title
        search_filters.append({"title": {"$regex": query, "$options": "i"}})
        
        # Build query
        if len(search_filters) > 1:
            final_query = {"$or": search_filters}
        elif len(search_filters) == 1:
            final_query = search_filters[0]
        else:
            final_query = {}
        
        # Execute search
        lessons = list(db.lessons.find(final_query).limit(limit))
        client.close()
        
        # Format results
        results = []
        for lesson in lessons:
            results.append({
                "_id": str(lesson.get("_id")),
                "lessonId": lesson.get("lessonId"),
                "title": lesson.get("title", "No title"),
                "semester": str(lesson.get("semester")) if lesson.get("semester") else None,
                "level": str(lesson.get("level")) if lesson.get("level") else None,
                "subject": str(lesson.get("subject")) if lesson.get("subject") else None,
                "stage": str(lesson.get("stage")) if lesson.get("stage") else None
            })
        
        return {
            "query": query,
            "total_found": len(results),
            "lessons": results
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "query": query
        }


@app.get("/lesson-details/{lesson_identifier}")
def get_lesson_details(
    lesson_identifier: str,
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Get detailed information about a lesson by ObjectId or lessonId.
    Shows all related documents and ObjectId connections.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        # Find lesson using flexible search
        lesson = None
        try:
            obj_id = ObjectId(lesson_identifier)
            lesson = db.lessons.find_one({"_id": obj_id})
        except:
            try:
                numeric_id = int(lesson_identifier)
                lesson = db.lessons.find_one({"lessonId": numeric_id})
            except:
                lesson = db.lessons.find_one({"lessonId": lesson_identifier})
        
        if not lesson:
            client.close()
            return {"error": f"Lesson not found: {lesson_identifier}"}
        
        # Get related documents
        details = {
            "lesson": _oid_to_serializable(lesson),
            "related_documents": {}
        }
        
        # Get semester, level, subject, stage details
        if lesson.get("semester"):
            semester = db.semesters.find_one({"_id": lesson.get("semester")})
            details["related_documents"]["semester"] = _oid_to_serializable(semester)
        
        if lesson.get("level"):
            level = db.levels.find_one({"_id": lesson.get("level")})
            details["related_documents"]["level"] = _oid_to_serializable(level)
        
        if lesson.get("subject"):
            subject = db.subjects.find_one({"_id": lesson.get("subject")})
            details["related_documents"]["subject"] = _oid_to_serializable(subject)
        
        if lesson.get("stage"):
            stage = db.stages.find_one({"_id": lesson.get("stage")})
            details["related_documents"]["stage"] = _oid_to_serializable(stage)
        
        # Get lesson mapping goals
        lesson_map_goal_oids = _id_list_from_maybe_array(lesson.get("lessonMapGoals", []))
        if lesson_map_goal_oids:
            goals = list(db.lessonmappinggoals.find({"_id": {"$in": lesson_map_goal_oids}}))
            details["related_documents"]["goals"] = _oid_to_serializable(goals)
        
        # Get activities
        activities = list(db.lessonplanactivities.find({"lesson": lesson.get("_id")}))
        details["related_documents"]["activities"] = _oid_to_serializable(activities)
        
        # Get questions
        questions = list(db.questions.find({"lesson": lesson.get("_id")}))
        details["related_documents"]["questions"] = _oid_to_serializable(questions)
        
        client.close()
        return details
        
    except Exception as e:
        return {
            "error": str(e),
            "lesson_identifier": lesson_identifier
        }


@app.get("/download/{file_key:path}")
def download_file_from_s3(file_key: str):
    """
    Download a file from S3/R2 storage.
    
    Args:
        file_key: The S3 object key (path) of the file to download
    
    Returns:
        Redirect to the public URL or file content
    """
    try:
        s3_service = get_s3_service()
        
        # Get file info to check if it exists
        file_info = s3_service.get_file_info(file_key)
        
        if file_info["status"] == "error":
            return JSONResponse(
                status_code=404,
                content={"error": "File not found", "file_key": file_key}
            )
        
        # Get public URL
        public_url = s3_service.get_public_url(file_key)
        
        # Return redirect to public URL
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=public_url)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "file_key": file_key}
        )


@app.get("/list-files/")
def list_uploaded_files(
    prefix: str = Query("", description="Filter files by prefix"),
    limit: int = Query(50, description="Maximum number of files to return")
):
    """
    List files uploaded to S3/R2 storage.
    
    Args:
        prefix: Filter files by prefix (e.g., 'worksheets/')
        limit: Maximum number of files to return
    
    Returns:
        List of uploaded files with metadata
    """
    try:
        s3_service = get_s3_service()
        
        # List files
        files_result = s3_service.list_files(prefix=prefix, max_keys=limit)
        
        if files_result["status"] == "success":
            # Add public URLs to file info
            for file_info in files_result["files"]:
                file_info["public_url"] = s3_service.get_public_url(file_info["key"])
                file_info["download_url"] = f"/download/{file_info['key']}"
        
        return files_result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/generate-mindmap-image/")
def generate_mindmap_image(
    document_uuid: str = Query(..., description="Document UUID from AI database mindmaps collection"),
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(800, description="Image height in pixels"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Generate mindmap image from AI database and upload to S3.
    Returns public URL of the generated image.
    
    Args:
        document_uuid: Document UUID to find in mindmaps collection
        width: Image width in pixels (default: 1200)
        height: Image height in pixels (default: 800)
        mongo_uri: Override MongoDB URI
        db_name: Override DB name
    
    Returns:
        Dictionary with generation results and public URL
    """
    try:
        mindmap_service = get_mindmap_service()
        
        # Update the service with custom DB settings if provided
        if mongo_uri or db_name:
            # We need to handle custom DB settings
            effective_mongo_uri = mongo_uri or MONGO_URI
            effective_db_name = db_name or DB_NAME
            
            # For now, we'll use the default settings and note this limitation
            logger.warning("Custom mongo_uri/db_name not yet implemented for mindmap service")
        
        # Process mindmap from database
        result = mindmap_service.process_mindmap_from_db(
            document_uuid=document_uuid,
            width=width,
            height=height
        )
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "document_uuid": document_uuid
        }


@app.post("/generate-mindmap-image-from-json/")
def generate_mindmap_image_from_json(
    mindmap_data: Dict[str, Any],
    title: str = Query("custom_mindmap", description="Title for file naming"),
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(800, description="Image height in pixels")
):
    """
    Generate mindmap image from provided JSON data and upload to S3.
    
    Args:
        mindmap_data: The mindmap JSON data (in request body)
        title: Title for file naming
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        Dictionary with generation results and public URL
    """
    try:
        mindmap_service = get_mindmap_service()
        
        # Generate image from provided JSON
        result = mindmap_service.generate_image_from_json(
            mindmap_json=mindmap_data,
            title=title,
            width=width,
            height=height
        )
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "title": title
        }


@app.get("/test-mindmap-sample/")
def test_mindmap_sample(
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(800, description="Image height in pixels")
):
    """
    Test endpoint to generate a sample mindmap image.
    Useful for testing the mindmap image generation functionality.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        Dictionary with generation results and public URL
    """
    try:
        mindmap_service = get_mindmap_service()
        
        # Create sample mindmap data
        sample_data = mindmap_service.create_sample_mindmap_data()
        
        # Generate image
        result = mindmap_service.generate_image_from_json(
            mindmap_json=sample_data,
            title="sample_test_mindmap",
            width=width,
            height=height
        )
        
        # Add sample data to result for reference
        if result["status"] == "success":
            result["sample_data"] = sample_data
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/search-mindmaps/")
def search_mindmaps(
    query: str = Query(..., description="Search query: document UUID, filename, or text fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Search for mindmap documents in the AI database by UUID, filename, or text fragment.
    Returns mindmap information to help find the correct document_uuid for image generation.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        
        search_filters = []
        
        # Try document UUID search
        search_filters.append({"document_uuid": query})
        
        # Try filename search
        search_filters.append({"filename": {"$regex": query, "$options": "i"}})
        
        # Build query
        if len(search_filters) > 1:
            final_query = {"$or": search_filters}
        elif len(search_filters) == 1:
            final_query = search_filters[0]
        else:
            final_query = {}
        
        # Search in mindmaps collection
        mindmaps = list(db.mindmaps.find(final_query).limit(limit))
        
        client.close()
        
        # Format results
        results = []
        for doc in mindmaps:
            mindmap_data = doc.get("mindmap", {})
            node_count = len(mindmap_data.get("nodeDataArray", [])) if mindmap_data else 0
            
            results.append({
                "_id": str(doc.get("_id")),
                "document_uuid": doc.get("document_uuid"),
                "filename": doc.get("filename"),
                "node_count": node_count,
                "has_mindmap_data": bool(mindmap_data),
                "generated_at": doc.get("generated_at")
            })
        
        return {
            "query": query,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "query": query
        }


@app.get("/mindmap-details/{document_uuid}")
def get_mindmap_details(
    document_uuid: str,
    include_full_data: bool = Query(False, description="Include full mindmap nodeDataArray"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    Get detailed information about a mindmap document by UUID from the AI database.
    Shows mindmap structure and metadata.
    """
    try:
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        # Get mindmap data using existing function
        mindmap_result = create_mindmap_from_ai_db(
            document_uuid=document_uuid,
            mongo_uri=effective_mongo_uri,
            db_name=effective_db_name,
            html_parsing=False,
            include_raw_meta=False
        )
        
        # Format the response
        details = {
            "document_uuid": document_uuid,
            "title": mindmap_result.get("title"),
            "node_count": mindmap_result.get("meta", {}).get("node_count", 0),
            "filename": mindmap_result.get("meta", {}).get("filename"),
            "meta": mindmap_result.get("meta", {})
        }
        
        # Include full mindmap data if requested
        if include_full_data:
            details["mindmap_data"] = mindmap_result.get("mindmap", {})
        else:
            # Include just a sample of nodes for preview
            mindmap_data = mindmap_result.get("mindmap", {})
            if mindmap_data and "nodeDataArray" in mindmap_data:
                nodes = mindmap_data["nodeDataArray"]
                details["sample_nodes"] = nodes[:5]  # First 5 nodes as preview
                details["total_nodes"] = len(nodes)
        
        return details
        
    except Exception as e:
        return {
            "error": str(e),
            "document_uuid": document_uuid
        }


# =============================================================================
# NEW ORGANIZED API STRUCTURE v2.0
# =============================================================================

# ===== GROUP 1: WORKSHEET AND QUESTIONS =====

@app.get("/api/v2/worksheets/generate")
def generate_worksheet_v2(
    document_uuid: str = Query(..., description="Document UUID from AI database"),
    output: str = Query("worksheet", description="worksheet or question_bank"),
    num_questions: int = Query(0, description="Number of questions to include (0 = all, legacy parameter)"),
    multiple_choice_count: int = Query(-1, description="Number of multiple choice questions (-1 = all, 0 = none, N = exact count)"),
    true_false_count: int = Query(-1, description="Number of true/false questions (-1 = all, 0 = none, N = exact count)"),
    short_answer_count: int = Query(-1, description="Number of short answer questions (-1 = all, 0 = none, N = exact count)"),
    complete_count: int = Query(-1, description="Number of complete/fill-in-blank questions (-1 = all, 0 = none, N = exact count)"),
    generate_pdf: bool = Query(True, description="Generate PDF files (default: True)"),
    html_parsing: bool = Query(False, description="Keep HTML markup (default: False)"),
    mongo_uri: str = Query(None, description="Override MongoDB URI (uses env MONGO_URI if not provided)"),
    db_name: str = Query(None, description="Override DB name (uses env DB_NAME if not provided)")
):
    """
    V2 API: Generate worksheet/question bank for a document from AI database.
    Returns files: JSON, DOCX, and optionally PDF.
    """
    # Reuse the existing function but with v2 response format
    result = generate_worksheet(document_uuid, output, num_questions, multiple_choice_count, 
                              true_false_count, short_answer_count, complete_count, 
                              generate_pdf, html_parsing, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "worksheets/generate",
        "success": "error" not in result,
        "data": result
    }


@app.get("/api/v2/questions/generate")
def generate_questions_v2(
    document_uuid: str = Query(..., description="Document UUID from AI database"),
    multiple_choice_count: int = Query(-1, description="Number of multiple choice questions (-1 = all, 0 = none, N = exact count)"),
    true_false_count: int = Query(-1, description="Number of true/false questions (-1 = all, 0 = none, N = exact count)"),
    short_answer_count: int = Query(-1, description="Number of short answer questions (-1 = all, 0 = none, N = exact count)"),
    complete_count: int = Query(-1, description="Number of complete/fill-in-blank questions (-1 = all, 0 = none, N = exact count)"),
    generate_pdf: bool = Query(True, description="Generate PDF files (default: True)"),
    html_parsing: bool = Query(False, description="Keep HTML markup (default: False)"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Generate question bank specifically. Alias for worksheet generation with output=question_bank.
    """
    result = generate_worksheet(document_uuid, "question_bank", 0, multiple_choice_count, 
                              true_false_count, short_answer_count, complete_count, 
                              generate_pdf, html_parsing, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "questions/generate",
        "success": "error" not in result,
        "data": result
    }


# ===== GROUP 2: MINDMAP =====

@app.get("/api/v2/mindmaps/generate")
def generate_mindmap_v2(
    document_uuid: str = Query(..., description="Document UUID from AI database mindmaps collection"),
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(800, description="Image height in pixels"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Generate mindmap image from AI database and upload to S3.
    """
    result = generate_mindmap_image(document_uuid, width, height, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "mindmaps/generate",
        "success": result.get("status") == "success",
        "data": result
    }


@app.post("/api/v2/mindmaps/generate-from-json")
def generate_mindmap_from_json_v2(
    mindmap_data: Dict[str, Any],
    title: str = Query("custom_mindmap", description="Title for file naming"),
    width: int = Query(1200, description="Image width in pixels"),
    height: int = Query(800, description="Image height in pixels")
):
    """
    V2 API: Generate mindmap image from provided JSON data and upload to S3.
    """
    result = generate_mindmap_image_from_json(mindmap_data, title, width, height)
    
    return {
        "api_version": "2.0",
        "endpoint": "mindmaps/generate-from-json",
        "success": result.get("status") == "success",
        "data": result
    }


@app.get("/api/v2/mindmaps/search")
def search_mindmaps_v2(
    query: str = Query(..., description="Search query: document UUID, filename, or text fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Search for mindmap documents in the AI database.
    """
    result = search_mindmaps(query, limit, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "mindmaps/search",
        "success": "error" not in result,
        "data": result
    }


@app.get("/api/v2/mindmaps/{document_uuid}")
def get_mindmap_details_v2(
    document_uuid: str,
    include_full_data: bool = Query(False, description="Include full mindmap nodeDataArray"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Get detailed information about a mindmap document by UUID.
    """
    result = get_mindmap_details(document_uuid, include_full_data, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "mindmaps/details",
        "success": "error" not in result,
        "data": result
    }


# ===== GROUP 3: STATUS AND HEALTH =====

@app.get("/api/v2/status/pdf")
def check_pdf_status_v2():
    """
    V2 API: Check the availability of PDF conversion tools on the server.
    """
    result = check_pdf_conversion_status()
    
    return {
        "api_version": "2.0",
        "endpoint": "status/pdf",
        "success": result.get("pdf_conversion_available", False),
        "data": result
    }


@app.get("/api/v2/status/s3")
def check_s3_status_v2():
    """
    V2 API: Check the availability and health of S3/R2 storage service.
    """
    result = check_s3_status()
    
    return {
        "api_version": "2.0",
        "endpoint": "status/s3",
        "success": result.get("status") == "healthy",
        "data": result
    }


@app.get("/api/v2/status/health")
def health_check_v2():
    """
    V2 API: Complete system health check including all services.
    """
    try:
        # Check PDF status
        pdf_status = check_pdf_conversion_status()
        
        # Check S3 status
        s3_status = check_s3_status()
        
        # Check MongoDB connection
        mongo_status = {"status": "unknown"}
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.server_info()  # Will raise exception if can't connect
            mongo_status = {"status": "healthy", "connection": "ok"}
            client.close()
        except Exception as e:
            mongo_status = {"status": "unhealthy", "error": str(e)}
        
        # Overall system status
        all_healthy = (
            pdf_status.get("pdf_conversion_available", False) and
            s3_status.get("status") == "healthy" and
            mongo_status.get("status") == "healthy"
        )
        
        return {
            "api_version": "2.0",
            "endpoint": "status/health",
            "success": all_healthy,
            "data": {
                "overall_status": "healthy" if all_healthy else "degraded",
                "services": {
                    "pdf_conversion": pdf_status,
                    "s3_storage": s3_status,
                    "mongodb": mongo_status
                },
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "api_version": "2.0",
            "endpoint": "status/health",
            "success": False,
            "data": {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }


# ===== GROUP 4: LESSONS AND DOCUMENTS =====

@app.get("/api/v2/documents/search")
def search_documents_v2(
    query: str = Query(..., description="Search query: document UUID, filename, or text fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Search for documents in the AI database by UUID, filename, or text fragment.
    """
    result = search_documents(query, limit, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "documents/search",
        "success": "error" not in result,
        "data": result
    }


@app.get("/api/v2/documents/{document_uuid}")
def get_document_details_v2(
    document_uuid: str,
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Get detailed information about a document by UUID from the AI database.
    """
    result = get_document_details(document_uuid, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "documents/details",
        "success": "error" not in result,
        "data": result
    }


@app.get("/api/v2/lessons/search")
def search_lessons_v2(
    query: str = Query(..., description="Search query: ObjectId, numeric lessonId, or title fragment"),
    limit: int = Query(10, description="Maximum number of results"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Search for lessons by ObjectId, lessonId, or title fragment (legacy support).
    """
    result = search_lessons(query, limit, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "lessons/search",
        "success": "error" not in result,
        "data": result
    }


@app.get("/api/v2/lessons/{lesson_identifier}")
def get_lesson_details_v2(
    lesson_identifier: str,
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Get detailed information about a lesson by ObjectId or lessonId (legacy support).
    """
    result = get_lesson_details(lesson_identifier, mongo_uri, db_name)
    
    return {
        "api_version": "2.0",
        "endpoint": "lessons/details",
        "success": "error" not in result,
        "data": result
    }


# ===== UNIFIED ENDPOINT: CREATE ALL =====

@app.post("/api/v2/create-all")
def create_all_documents(
    document_uuid: str = Query(..., description="Document UUID - if exists, specify override=true to replace"),
    override: bool = Query(False, description="Override existing documents if they exist"),
    
    # Worksheet question counts
    worksheet_multiple_choice_count: int = Query(-1, description="Number of multiple choice questions for worksheet (-1 = all, 0 = none, N = exact count)"),
    worksheet_true_false_count: int = Query(-1, description="Number of true/false questions for worksheet (-1 = all, 0 = none, N = exact count)"),
    worksheet_short_answer_count: int = Query(-1, description="Number of short answer questions for worksheet (-1 = all, 0 = none, N = exact count)"),
    worksheet_complete_count: int = Query(-1, description="Number of complete/fill-in-blank questions for worksheet (-1 = all, 0 = none, N = exact count)"),
    
    # Question bank question counts
    question_bank_multiple_choice_count: int = Query(-1, description="Number of multiple choice questions for question bank (-1 = all, 0 = none, N = exact count)"),
    question_bank_true_false_count: int = Query(-1, description="Number of true/false questions for question bank (-1 = all, 0 = none, N = exact count)"),
    question_bank_short_answer_count: int = Query(-1, description="Number of short answer questions for question bank (-1 = all, 0 = none, N = exact count)"),
    question_bank_complete_count: int = Query(-1, description="Number of complete/fill-in-blank questions for question bank (-1 = all, 0 = none, N = exact count)"),
    
    # Mindmap parameters  
    mindmap_width: int = Query(1200, description="Mindmap image width in pixels"),
    mindmap_height: int = Query(800, description="Mindmap image height in pixels"),
    
    # General parameters
    generate_pdf: bool = Query(False, description="Generate PDF files (default: False - generates DOCX)"),
    html_parsing: bool = Query(False, description="Keep HTML markup"),
    mongo_uri: str = Query(None, description="Override MongoDB URI"),
    db_name: str = Query(None, description="Override DB name")
):
    """
    V2 API: Unified endpoint to create mindmap, worksheet, and question bank for a document.
    Creates folder structure: all_data/document_uuid/{mindmap.png, worksheet_with_solutions.[docx/pdf], worksheet_no_solutions.[docx/pdf], question_bank_with_solutions.[docx/pdf], question_bank_no_solutions.[docx/pdf]}
    
    Default format is DOCX. Files are converted to PDF only if generate_pdf=True.
    Each document type (worksheet vs question bank) can have different question counts.
    Generates both versions with and without solutions for worksheet and question bank.
    
    If document UUID exists and override=False, returns existing file paths.
    If override=True, regenerates all files.
    """
    try:
        import uuid as uuid_module
        import os
        import tempfile
        
        # Validate UUID format
        try:
            uuid_module.UUID(document_uuid)
        except ValueError:
            return {
                "api_version": "2.0",
                "endpoint": "create-all",
                "success": False,
                "error": "Invalid document UUID format"
            }
        
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME
        
        # Folder structure: all_data/document_uuid/
        folder_path = f"all_data/{document_uuid}"
        
        # Check for existing files in S3
        s3_service = get_s3_service()
        try:
            response = s3_service.s3_client.list_objects_v2(
                Bucket=s3_service.bucket_name,
                Prefix=folder_path
            )
            
            existing_files = {}
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    public_url = f"{s3_service.endpoint_url.replace('dcdb150a91310324ecc43b417e14446b.r2.cloudflarestorage.com', 'pub-dcdb150a91310324ecc43b417e14446b.r2.dev')}/{key}"
                    
                    if key.endswith('mindmap.png'):
                        existing_files['mindmap'] = public_url
                    elif 'worksheet_with_solutions.' in key:
                        existing_files['worksheet_with_solutions'] = public_url
                    elif 'worksheet_no_solutions.' in key:
                        existing_files['worksheet_no_solutions'] = public_url
                    elif 'question_bank_with_solutions.' in key:
                        existing_files['question_bank_with_solutions'] = public_url
                    elif 'question_bank_no_solutions.' in key:
                        existing_files['question_bank_no_solutions'] = public_url
                        
        except Exception as e:
            logger.warning(f"Could not check existing files: {e}")
            existing_files = {}
        
        # If files exist and override is False, return existing paths
        if existing_files and not override:
            return {
                "api_version": "2.0",
                "endpoint": "create-all",
                "success": True,
                "data": {
                    "document_uuid": document_uuid,
                    "folder_path": folder_path,
                    "exists": True,
                    "override_required": True,
                    "existing_files": existing_files,
                    "message": "Documents already exist. Use override=true to regenerate."
                }
            }
        
        # Create all documents
        results = {
            "document_uuid": document_uuid,
            "folder_path": folder_path,
            "created_files": {},
            "errors": {},
            "status": "success"
        }
        
        # 1. Generate Mindmap
        try:
            # Get mindmap data from database first
            mindmap_result = create_mindmap_from_ai_db(
                document_uuid=document_uuid,
                mongo_uri=effective_mongo_uri,
                db_name=effective_db_name,
                html_parsing=False,
                include_raw_meta=False
            )
            
            mindmap_data = mindmap_result.get("mindmap", {})
            title = mindmap_result.get("title", f"mindmap_{document_uuid}")
            
            if mindmap_data:
                # Generate image using mindmap service
                mindmap_service = get_mindmap_service()
                image_result = mindmap_service.generate_image_from_json(
                    mindmap_json=mindmap_data,
                    title=title,
                    width=mindmap_width,
                    height=mindmap_height
                )
                
                if image_result["status"] == "success" and image_result.get("s3_key"):
                    # Copy the file to the structured location
                    mindmap_s3_key = f"{folder_path}/mindmap.png"
                    
                    try:
                        copy_source = {
                            'Bucket': s3_service.bucket_name,
                            'Key': image_result["s3_key"]
                        }
                        s3_service.s3_client.copy_object(
                            CopySource=copy_source,
                            Bucket=s3_service.bucket_name,
                            Key=mindmap_s3_key,
                            MetadataDirective='COPY'
                        )
                        
                        # Generate public URL
                        mindmap_url = f"{s3_service.endpoint_url.replace('dcdb150a91310324ecc43b417e14446b.r2.cloudflarestorage.com', 'pub-dcdb150a91310324ecc43b417e14446b.r2.dev')}/{mindmap_s3_key}"
                        
                        results["created_files"]["mindmap"] = {
                            "type": "mindmap",
                            "format": "png",
                            "s3_key": mindmap_s3_key,
                            "public_url": mindmap_url,
                            "standard_name": "mindmap"
                        }
                        
                        # Optionally delete the original file
                        try:
                            s3_service.s3_client.delete_object(
                                Bucket=s3_service.bucket_name,
                                Key=image_result["s3_key"]
                            )
                        except:
                            pass  # Ignore deletion errors
                            
                    except Exception as copy_error:
                        results["errors"]["mindmap"] = f"Failed to copy mindmap to structured folder: {copy_error}"
                        results["status"] = "partial"
                else:
                    results["errors"]["mindmap"] = image_result.get("message", "Failed to generate mindmap image")
                    results["status"] = "partial"
            else:
                results["errors"]["mindmap"] = "No mindmap data found for this document"
                results["status"] = "partial"
        except Exception as e:
            logger.error(f"Mindmap generation error: {e}")
            results["errors"]["mindmap"] = str(e)
            results["status"] = "partial"
        
        # 2. Generate Worksheet with solutions
        try:
            worksheet_result = generate_worksheet_with_custom_counts(
                document_uuid, effective_mongo_uri, effective_db_name,
                worksheet_multiple_choice_count, worksheet_true_false_count,
                worksheet_short_answer_count, worksheet_complete_count,
                include_solutions=True, generate_pdf=generate_pdf
            )
            
            if worksheet_result["status"] == "success":
                # Upload worksheet with specific folder structure
                file_extension = worksheet_result.get("format", "docx")
                worksheet_s3_key = f"{folder_path}/worksheet_with_solutions.{file_extension}"
                
                # Determine content type
                content_type = 'application/pdf' if file_extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                
                # Upload the file
                upload_result = s3_service.upload_file(
                    local_file_path=worksheet_result["file_path"],
                    s3_key=worksheet_s3_key,
                    content_type=content_type
                )
                
                if upload_result["status"] == "success":
                    results["created_files"]["worksheet_with_solutions"] = {
                        "type": "worksheet",
                        "format": file_extension,
                        "solutions": True,
                        "s3_key": worksheet_s3_key,
                        "public_url": upload_result["public_url"],
                        "standard_name": "worksheet_with_solutions"
                    }
                    
                    # Clean up local file
                    try:
                        os.remove(worksheet_result["file_path"])
                    except:
                        pass
                else:
                    results["errors"]["worksheet_with_solutions"] = upload_result.get("message", "Upload failed")
                    results["status"] = "partial"
            else:
                results["errors"]["worksheet_with_solutions"] = worksheet_result.get("message", "Generation failed")
                results["status"] = "partial"
        except Exception as e:
            results["errors"]["worksheet_with_solutions"] = str(e)
            results["status"] = "partial"
        
        # 3. Generate Worksheet without solutions
        try:
            worksheet_result = generate_worksheet_with_custom_counts(
                document_uuid, effective_mongo_uri, effective_db_name,
                worksheet_multiple_choice_count, worksheet_true_false_count,
                worksheet_short_answer_count, worksheet_complete_count,
                include_solutions=False, generate_pdf=generate_pdf
            )
            
            if worksheet_result["status"] == "success":
                # Upload worksheet with specific folder structure
                file_extension = worksheet_result.get("format", "docx")
                worksheet_s3_key = f"{folder_path}/worksheet_no_solutions.{file_extension}"
                
                # Determine content type
                content_type = 'application/pdf' if file_extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                
                # Upload the file
                upload_result = s3_service.upload_file(
                    local_file_path=worksheet_result["file_path"],
                    s3_key=worksheet_s3_key,
                    content_type=content_type
                )
                
                if upload_result["status"] == "success":
                    results["created_files"]["worksheet_no_solutions"] = {
                        "type": "worksheet",
                        "format": file_extension,
                        "solutions": False,
                        "s3_key": worksheet_s3_key,
                        "public_url": upload_result["public_url"],
                        "standard_name": "worksheet_no_solutions"
                    }
                    
                    # Clean up local file
                    try:
                        os.remove(worksheet_result["file_path"])
                    except:
                        pass
                else:
                    results["errors"]["worksheet_no_solutions"] = upload_result.get("message", "Upload failed")
                    results["status"] = "partial"
            else:
                results["errors"]["worksheet_no_solutions"] = worksheet_result.get("message", "Generation failed")
                results["status"] = "partial"
        except Exception as e:
            results["errors"]["worksheet_no_solutions"] = str(e)
            results["status"] = "partial"
        
        # 4. Generate Question Bank with solutions
        try:
            question_result = generate_question_bank_with_custom_counts(
                document_uuid, effective_mongo_uri, effective_db_name,
                question_bank_multiple_choice_count, question_bank_true_false_count,
                question_bank_short_answer_count, question_bank_complete_count,
                include_solutions=True, generate_pdf=generate_pdf
            )
            
            if question_result["status"] == "success":
                # Upload question bank with specific folder structure
                file_extension = question_result.get("format", "docx")
                question_s3_key = f"{folder_path}/question_bank_with_solutions.{file_extension}"
                
                # Determine content type
                content_type = 'application/pdf' if file_extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                
                # Upload the file
                upload_result = s3_service.upload_file(
                    local_file_path=question_result["file_path"],
                    s3_key=question_s3_key,
                    content_type=content_type
                )
                
                if upload_result["status"] == "success":
                    results["created_files"]["question_bank_with_solutions"] = {
                        "type": "question_bank",
                        "format": file_extension,
                        "solutions": True,
                        "s3_key": question_s3_key,
                        "public_url": upload_result["public_url"],
                        "standard_name": "question_bank_with_solutions"
                    }
                    
                    # Clean up local file
                    try:
                        os.remove(question_result["file_path"])
                    except:
                        pass
                else:
                    results["errors"]["question_bank_with_solutions"] = upload_result.get("message", "Upload failed")
                    results["status"] = "partial"
            else:
                results["errors"]["question_bank_with_solutions"] = question_result.get("message", "Generation failed")
                results["status"] = "partial"
        except Exception as e:
            results["errors"]["question_bank_with_solutions"] = str(e)
            results["status"] = "partial"
        
        # 5. Generate Question Bank without solutions
        try:
            question_result = generate_question_bank_with_custom_counts(
                document_uuid, effective_mongo_uri, effective_db_name,
                question_bank_multiple_choice_count, question_bank_true_false_count,
                question_bank_short_answer_count, question_bank_complete_count,
                include_solutions=False, generate_pdf=generate_pdf
            )
            
            if question_result["status"] == "success":
                # Upload question bank with specific folder structure
                file_extension = question_result.get("format", "docx")
                question_s3_key = f"{folder_path}/question_bank_no_solutions.{file_extension}"
                
                # Determine content type
                content_type = 'application/pdf' if file_extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                
                # Upload the file
                upload_result = s3_service.upload_file(
                    local_file_path=question_result["file_path"],
                    s3_key=question_s3_key,
                    content_type=content_type
                )
                
                if upload_result["status"] == "success":
                    results["created_files"]["question_bank_no_solutions"] = {
                        "type": "question_bank",
                        "format": file_extension,
                        "solutions": False,
                        "s3_key": question_s3_key,
                        "public_url": upload_result["public_url"],
                        "standard_name": "question_bank_no_solutions"
                    }
                    
                    # Clean up local file
                    try:
                        os.remove(question_result["file_path"])
                    except:
                        pass
                else:
                    results["errors"]["question_bank_no_solutions"] = upload_result.get("message", "Upload failed")
                    results["status"] = "partial"
            else:
                results["errors"]["question_bank_no_solutions"] = question_result.get("message", "Generation failed")
                results["status"] = "partial"
        except Exception as e:
            results["errors"]["question_bank_no_solutions"] = str(e)
            results["status"] = "partial"
        
        # Determine final status
        if len(results["created_files"]) == 0:
            results["status"] = "error"
        elif len(results["errors"]) > 0:
            results["status"] = "partial"
        
        results["summary"] = {
            "total_requested": 5,  # mindmap, worksheet_with_solutions, worksheet_no_solutions, question_bank_with_solutions, question_bank_no_solutions
            "successfully_created": len(results["created_files"]),
            "failed": len(results["errors"]),
            "success_rate": f"{len(results['created_files'])}/5"
        }
        
        # Add question count summary
        results["question_counts"] = {
            "worksheet": {
                "multiple_choice": worksheet_multiple_choice_count,
                "true_false": worksheet_true_false_count,
                "short_answer": worksheet_short_answer_count,
                "complete": worksheet_complete_count
            },
            "question_bank": {
                "multiple_choice": question_bank_multiple_choice_count,
                "true_false": question_bank_true_false_count,
                "short_answer": question_bank_short_answer_count,
                "complete": question_bank_complete_count
            }
        }
        
        results["created_at"] = datetime.now().isoformat()
        
        return {
            "api_version": "2.0",
            "endpoint": "create-all",
            "success": results["status"] in ["success", "partial"],
            "data": results
        }
        
    except Exception as e:
        return {
            "api_version": "2.0",
            "endpoint": "create-all", 
            "success": False,
            "error": str(e),
            "document_uuid": document_uuid
        }


# ===== FILE MANAGEMENT =====

@app.get("/api/v2/files/list")
def list_files_v2(
    prefix: str = Query("", description="Filter files by prefix"),
    limit: int = Query(50, description="Maximum number of files to return")
):
    """
    V2 API: List files uploaded to S3/R2 storage.
    """
    result = list_uploaded_files(prefix, limit)
    
    return {
        "api_version": "2.0",
        "endpoint": "files/list",
        "success": result.get("status") == "success",
        "data": result
    }


@app.get("/api/v2/files/download/{file_key:path}")
def download_file_v2(file_key: str):
    """
    V2 API: Download a file from S3/R2 storage.
    """
    # This returns a redirect, so we'll use the original function
    return download_file_from_s3(file_key)


# ===== API INFORMATION =====

@app.get("/api/v2/info")
def api_info_v2():
    """
    V2 API: Get API information and available endpoints.
    """
    return {
        "api_version": "2.0",
        "title": "QA Worksheet Generator API",
        "description": "Unified API for generating worksheets, questions, and mindmaps",
        "endpoint_groups": {
            "worksheets_and_questions": {
                "description": "Generate worksheets and question banks",
                "endpoints": [
                    "/api/v2/worksheets/generate",
                    "/api/v2/questions/generate"
                ]
            },
            "mindmaps": {
                "description": "Generate and manage mindmap images",
                "endpoints": [
                    "/api/v2/mindmaps/generate",
                    "/api/v2/mindmaps/generate-from-json",
                    "/api/v2/mindmaps/search",
                    "/api/v2/mindmaps/{document_uuid}"
                ]
            },
            "status_and_health": {
                "description": "System status and health checks",
                "endpoints": [
                    "/api/v2/status/pdf",
                    "/api/v2/status/s3",
                    "/api/v2/status/health"
                ]
            },
            "lessons_and_documents": {
                "description": "Search and manage documents and lessons",
                "endpoints": [
                    "/api/v2/documents/search",
                    "/api/v2/documents/{document_uuid}",
                    "/api/v2/lessons/search",
                    "/api/v2/lessons/{lesson_identifier}"
                ]
            },
            "unified": {
                "description": "Create all document types at once",
                "endpoints": [
                    "/api/v2/create-all"
                ]
            },
            "file_management": {
                "description": "File storage and retrieval",
                "endpoints": [
                    "/api/v2/files/list",
                    "/api/v2/files/download/{file_key:path}"
                ]
            }
        },
        "features": {
            "uuid_based_document_management": True,
            "override_existing_documents": True,
            "s3_file_storage": True,
            "pdf_generation": True,
            "arabic_language_support": True,
            "mindmap_image_generation": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    
    print(f"Starting QA Worksheet Generator API v2.0")
    print(f"Server: http://{host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"API Info: http://{host}:{port}/api/v2/info")
    
    uvicorn.run(app, host=host, port=port, reload=debug)
