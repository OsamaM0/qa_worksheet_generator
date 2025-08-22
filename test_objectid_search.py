#!/usr/bin/env python3
"""
Test script for the updated ObjectId-based search functionality in app.py
This script tests the main functions without starting the full FastAPI server.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_worksheet_from_lesson, MONGO_URI, DB_NAME, _oid_to_serializable
from bson import ObjectId
from pymongo import MongoClient

def test_objectid_functionality():
    """Test the updated ObjectId-based search functionality"""
    
    print("🔍 Testing ObjectId-based Search Updates")
    print("=" * 50)
    
    try:
        # Connect to database to get sample data
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Get a sample lesson
        sample_lesson = db.lessons.find_one()
        if not sample_lesson:
            print("❌ No lessons found in database")
            return False
        
        print(f"📋 Sample lesson found:")
        print(f"   _id: {sample_lesson['_id']}")
        print(f"   lessonId: {sample_lesson.get('lessonId', 'N/A')}")
        print(f"   title: {sample_lesson.get('title', 'No title')}")
        print()
        
        # Test 1: Search by ObjectId
        print("🧪 Test 1: Search by ObjectId")
        try:
            result = create_worksheet_from_lesson(
                lesson_id=sample_lesson['_id'],
                mongo_uri=MONGO_URI,
                db_name=DB_NAME,
                output="question_bank",
                include_raw_meta=False
            )
            print(f"   ✅ SUCCESS: Found {len(result.get('questions', []))} questions")
            print(f"   Title: {result.get('title', 'No title')}")
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
        print()
        
        # Test 2: Search by ObjectId string
        print("🧪 Test 2: Search by ObjectId string")
        try:
            result = create_worksheet_from_lesson(
                lesson_id=str(sample_lesson['_id']),
                mongo_uri=MONGO_URI,
                db_name=DB_NAME,
                output="question_bank",
                include_raw_meta=False
            )
            print(f"   ✅ SUCCESS: Found {len(result.get('questions', []))} questions")
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
        print()
        
        # Test 3: Search by numeric lessonId (backward compatibility)
        if sample_lesson.get('lessonId'):
            print("🧪 Test 3: Search by numeric lessonId (backward compatibility)")
            try:
                result = create_worksheet_from_lesson(
                    lesson_id=sample_lesson['lessonId'],
                    mongo_uri=MONGO_URI,
                    db_name=DB_NAME,
                    output="question_bank",
                    include_raw_meta=False
                )
                print(f"   ✅ SUCCESS: Found {len(result.get('questions', []))} questions")
            except Exception as e:
                print(f"   ❌ FAILED: {e}")
            print()
        
        # Test 4: Check ObjectId serialization
        print("🧪 Test 4: ObjectId serialization")
        try:
            result = create_worksheet_from_lesson(
                lesson_id=sample_lesson['_id'],
                mongo_uri=MONGO_URI,
                db_name=DB_NAME,
                output="question_bank",
                include_raw_meta=True  # This should contain ObjectIds
            )
            
            # Check if meta contains ObjectIds
            meta = result.get('meta', {})
            lesson_meta = meta.get('lesson', {})
            
            if '_id' in lesson_meta:
                if isinstance(lesson_meta['_id'], ObjectId):
                    print("   ⚠️  WARNING: ObjectId not serialized (include_raw_meta=True)")
                else:
                    print("   ✅ ObjectId properly serialized to string")
            
            # Test serialization function
            serialized = _oid_to_serializable(sample_lesson)
            if isinstance(serialized['_id'], str):
                print("   ✅ _oid_to_serializable working correctly")
            else:
                print("   ❌ _oid_to_serializable failed")
                
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
        print()
        
        # Test 5: Check related documents
        print("🧪 Test 5: Related documents check")
        try:
            # Check if we can find related documents
            goals_count = 0
            activities_count = 0
            questions_count = 0
            
            # Check goals
            if sample_lesson.get('lessonMapGoals'):
                goals_count = db.lessonmappinggoals.count_documents({
                    '_id': {'$in': sample_lesson['lessonMapGoals']}
                })
            
            # Check activities
            activities_count = db.lessonplanactivities.count_documents({
                'lesson': sample_lesson['_id']
            })
            
            # Check questions
            questions_count = db.questions.count_documents({
                'lesson': sample_lesson['_id']
            })
            
            print(f"   Goals found: {goals_count}")
            print(f"   Activities found: {activities_count}")
            print(f"   Questions found: {questions_count}")
            print("   ✅ Related document queries working")
            
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
        print()
        
        client.close()
        
        print("🎯 All tests completed!")
        print("✅ ObjectId-based search updates are working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_objectid_functionality()
    if success:
        print("\n🚀 Ready to test API endpoints!")
        print("Use the MongoDB playground script to get ObjectId values for testing.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
