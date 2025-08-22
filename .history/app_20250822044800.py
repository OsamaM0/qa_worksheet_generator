
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration from environment
MONGO_URI = os.getenv("MONGO_URI", "mongodb://ai:VgjVpcllJjhYy2c@65.109.31.94:27017/ien?authSource=ien")
DB_NAME = os.getenv("DB_NAME", "ien")

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

    activity_goal_ids = []
    for act in activities:
        activity_goal_ids.extend(parse_comma_ids(act.get("goals", "")))
    goal_numeric_ids = [g.get("id") for g in goals_docs if g.get("id")]
    goal_numeric_ids = list(set(goal_numeric_ids + activity_goal_ids))

    q_filters = []
    q_filters.append({"lessonId": lesson.get("lessonId")})
    if goal_numeric_ids:
        q_filters.append({"goalId": {"$in": goal_numeric_ids}})
    if lesson.get("lessonPlanId"):
        q_filters.append({"lessonPlanId": lesson.get("lessonPlanId")})
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


class PDFConverter:
    """Convert DOCX to PDF with Arabic support and logo watermark"""
    
    def __init__(self, logo_path: str = None):
        self.logo_path = logo_path or "logo.png"
    
    def convert_docx_to_pdf(self, docx_path: str, output_path: str) -> bool:
        """Convert DOCX file to PDF with logo watermark"""
        try:
            # Try different methods for DOCX to PDF conversion
            methods = [
                self._convert_with_python_docx2pdf,
                self._convert_with_comtypes,
                self._convert_with_libreoffice,
                self._fallback_to_copy
            ]
            
            for method in methods:
                try:
                    if method(docx_path, output_path):
                        # Add watermark if conversion was successful
                        self._add_watermark_to_pdf(output_path)
                        return True
                except Exception as e:
                    print(f"Method {method.__name__} failed: {e}")
                    continue
            
            return False
        except Exception as e:
            print(f"PDF conversion error: {e}")
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
        """Try converting using LibreOffice command line"""
        try:
            import subprocess
            
            # Try common LibreOffice paths
            libreoffice_paths = [
                "libreoffice",
                "soffice",
                "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
                "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"
            ]
            
            for lo_path in libreoffice_paths:
                try:
                    output_dir = os.path.dirname(output_path)
                    cmd = [
                        lo_path,
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", output_dir,
                        docx_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        # LibreOffice creates PDF with same name as DOCX
                        generated_pdf = os.path.join(output_dir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
                        if os.path.exists(generated_pdf):
                            if generated_pdf != output_path:
                                os.rename(generated_pdf, output_path)
                            return True
                    break
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            
            return False
        except Exception as e:
            print(f"LibreOffice conversion failed: {e}")
            return False
    
    def _fallback_to_copy(self, docx_path: str, output_path: str) -> bool:
        """Fallback: copy DOCX as 'PDF' (not a real conversion)"""
        try:
            import shutil
            shutil.copy2(docx_path, output_path.replace('.pdf', '_as_docx.docx'))
            print(f"Could not convert to PDF, copied DOCX file instead")
            return False  # Return False since it's not a real PDF
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
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_lesson_title(lesson_doc, html_parsing):
    return _strip_html(lesson_doc.get('title', 'lesson'), html_parsing)

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

@app.get("/generate-worksheet/")
def generate_worksheet(
    lesson_id: int = Query(..., description="Lesson ID"),
    output: str = Query("worksheet", description="worksheet or question_bank"),
    num_questions: int = Query(0, description="Number of questions to include (0 = all)"),
    generate_pdf: bool = Query(True, description="Generate PDF files (default: True)"),
    html_parsing: bool = Query(False, description="Keep HTML markup (default: False)"),
    mongo_uri: str = Query(None, description="Override MongoDB URI (uses env MONGO_URI if not provided)"),
    db_name: str = Query(None, description="Override DB name (uses env DB_NAME if not provided)")
):
    """
    Generate worksheet/question bank for a lesson. Returns files: JSON, DOCX, and optionally PDF.
    """
    try:
        # Use environment variables as defaults
        effective_mongo_uri = mongo_uri or MONGO_URI
        effective_db_name = db_name or DB_NAME

        # Get worksheet/question bank data
        data = create_worksheet_from_lesson(
            lesson_id=lesson_id,
            mongo_uri=effective_mongo_uri,
            db_name=effective_db_name,
            html_parsing=html_parsing,
            output=output,
            include_raw_meta=False
        )

        # Limit number of questions if requested
        if num_questions and num_questions > 0:
            data = _limit_questions(data, num_questions)

        # Get lesson title for file naming
        client = MongoClient(effective_mongo_uri)
        db = client[effective_db_name]
        lesson_doc = db.lessons.find_one({"lessonId": lesson_id})
        client.close()
        lesson_title = _get_lesson_title(lesson_doc, html_parsing) if lesson_doc else f"lesson_{lesson_id}"
        
        # Clean lesson title for filename
        lesson_title_clean = re.sub(r'[<>:"/\\|?*]', '_', lesson_title)
        suffix = "_ورقة_عمل" if output == "worksheet" else "_بنك_أسئله"
        base_filename = f"{lesson_title_clean}{suffix}"

        # Create copies for solutions and no solutions
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
            "lesson_title": lesson_title,
            "base_filename": base_filename,
            "generate_pdf": generate_pdf,
            "files": {}
        }

        # Generate JSON files
        try:
            json_no_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_no_solutions.json")
            with open(json_no_solutions, "w", encoding="utf-8") as f:
                f.write(json_util.dumps(data_no_solutions, ensure_ascii=False, indent=2))
            result["files"]["json_no_solutions"] = json_no_solutions

            json_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.json")
            with open(json_with_solutions, "w", encoding="utf-8") as f:
                f.write(json_util.dumps(data_with_solutions, ensure_ascii=False, indent=2))
            result["files"]["json_with_solutions"] = json_with_solutions
        except Exception as e:
            result["files"]["json_error"] = str(e)

        # Generate DOCX files using WorksheetService
        try:
            service = WorksheetService()
            
            docx_no_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_no_solutions.docx")
            docx_result_no_sol = service.create_worksheet(data_no_solutions, docx_no_solutions)
            if docx_result_no_sol["status"] == "success":
                result["files"]["docx_no_solutions"] = docx_no_solutions
            else:
                result["files"]["docx_no_solutions_error"] = docx_result_no_sol["message"]

            docx_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.docx")
            docx_result_with_sol = service.create_worksheet(data_with_solutions, docx_with_solutions)
            if docx_result_with_sol["status"] == "success":
                result["files"]["docx_with_solutions"] = docx_with_solutions
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
                    else:
                        result["files"]["pdf_no_solutions_error"] = "DOCX to PDF conversion failed"

                if "docx_with_solutions" in result["files"]:
                    pdf_with_solutions = os.path.join(tempfile.gettempdir(), f"{base_filename}_with_solutions.pdf")
                    if pdf_converter.convert_docx_to_pdf(result["files"]["docx_with_solutions"], pdf_with_solutions):
                        result["files"]["pdf_with_solutions"] = pdf_with_solutions
                    else:
                        result["files"]["pdf_with_solutions_error"] = "DOCX to PDF conversion failed"
                    
            except Exception as e:
                result["files"]["pdf_error"] = str(e)
        else:
            result["files"]["pdf_skipped"] = "PDF generation disabled by user"

        return result

    except Exception as e:
        return {
            "error": str(e),
            "lesson_id": lesson_id,
            "output": output
        }


if __name__ == "__main__":
    
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)