/* global use, db */
// MongoDB Playground - Test ObjectId-based Search Updates
// This script tests the new ObjectId-based search logic from the updated app.py

// The current database to use.
use('ien');

print("🔍 TESTING OBJECTID-BASED SEARCH UPDATES");
print("========================================");
print(`Database: ien`);
print(`Timestamp: ${new Date().toISOString()}`);
print("");

// =============================================================================
// PART 1: Test Lesson Search by ObjectId
// =============================================================================
print("📋 PART 1: LESSON SEARCH TESTS");
print("==============================");

// Get a sample lesson to test with
const sampleLesson = db.lessons.findOne();
if (sampleLesson) {
    print(`✅ Sample lesson found:`);
    print(`   _id: ${sampleLesson._id}`);
    print(`   lessonId: ${sampleLesson.lessonId || 'No lessonId'}`);
    print(`   title: ${sampleLesson.title || 'No title'}`);
    
    // Test ObjectId search
    const byObjectId = db.lessons.findOne({_id: sampleLesson._id});
    print(`   ✓ Search by _id: ${byObjectId ? 'SUCCESS' : 'FAILED'}`);
    
    // Test lessonId search (backward compatibility)
    if (sampleLesson.lessonId) {
        const byLessonId = db.lessons.findOne({lessonId: sampleLesson.lessonId});
        print(`   ✓ Search by lessonId: ${byLessonId ? 'SUCCESS' : 'FAILED'}`);
    }
    
    print("");
    
    // =============================================================================
    // PART 2: Test Related Document Searches
    // =============================================================================
    print("🔗 PART 2: RELATED DOCUMENT SEARCHES");
    print("====================================");
    
    // Test lesson mapping goals by ObjectId
    if (sampleLesson.lessonMapGoals && Array.isArray(sampleLesson.lessonMapGoals)) {
        print(`--- Lesson Mapping Goals ---`);
        print(`   lessonMapGoals array length: ${sampleLesson.lessonMapGoals.length}`);
        
        const goalResults = db.lessonmappinggoals.find({_id: {$in: sampleLesson.lessonMapGoals}}).toArray();
        print(`   ✓ Goals found by _id: ${goalResults.length}`);
        
        goalResults.forEach((goal, idx) => {
            print(`     [${idx + 1}] ${goal._id}: ${goal.title || goal.name || 'No title'}`);
        });
        print("");
    }
    
    // Test activities by lesson ObjectId
    print(`--- Activities ---`);
    const activities = db.lessonplanactivities.find({lesson: sampleLesson._id}).toArray();
    print(`   ✓ Activities found by lesson._id: ${activities.length}`);
    
    if (activities.length > 0) {
        activities.forEach((activity, idx) => {
            print(`     [${idx + 1}] ${activity._id}: ${activity.title || activity.name || 'No title'}`);
            if (activity.goals) {
                print(`         Goals field: ${activity.goals}`);
            }
        });
    }
    print("");
    
    // Test questions by lesson ObjectId
    print(`--- Questions ---`);
    const questionsByLesson = db.questions.find({lesson: sampleLesson._id}).toArray();
    print(`   ✓ Questions found by lesson._id: ${questionsByLesson.length}`);
    
    // Also test old lessonId search for comparison
    if (sampleLesson.lessonId) {
        const questionsByLessonId = db.questions.find({lessonId: sampleLesson.lessonId}).toArray();
        print(`   ℹ️  Questions found by lessonId (old): ${questionsByLessonId.length}`);
    }
    
    if (questionsByLesson.length > 0) {
        questionsByLesson.slice(0, 3).forEach((question, idx) => {
            print(`     [${idx + 1}] ${question._id}: ${question.title || 'No title'}`);
        });
    }
    print("");
    
    // Test reference documents (semester, level, subject, stage)
    print(`--- Reference Documents ---`);
    
    if (sampleLesson.semester) {
        const semester = db.semesters.findOne({_id: sampleLesson.semester});
        print(`   ✓ Semester: ${semester ? semester.title || semester.name || 'Found' : 'NOT FOUND'}`);
    }
    
    if (sampleLesson.level) {
        const level = db.levels.findOne({_id: sampleLesson.level});
        print(`   ✓ Level: ${level ? level.title || level.name || 'Found' : 'NOT FOUND'}`);
    }
    
    if (sampleLesson.subject) {
        const subject = db.subjects.findOne({_id: sampleLesson.subject});
        print(`   ✓ Subject: ${subject ? subject.title || subject.name || 'Found' : 'NOT FOUND'}`);
    }
    
    if (sampleLesson.stage) {
        const stage = db.stages.findOne({_id: sampleLesson.stage});
        print(`   ✓ Stage: ${stage ? stage.title || stage.name || 'Found' : 'NOT FOUND'}`);
    }
    
} else {
    print("❌ No lessons found in database");
}

print("");

// =============================================================================
// PART 3: API Endpoint Test Queries
// =============================================================================
print("🚀 PART 3: API ENDPOINT TEST QUERIES");
print("====================================");

if (sampleLesson) {
    print("Use these values to test your updated API endpoints:");
    print("");
    print(`// Test generate-worksheet endpoint with ObjectId:`);
    print(`GET /generate-worksheet/?lesson_id=${sampleLesson._id}`);
    print("");
    
    if (sampleLesson.lessonId) {
        print(`// Test generate-worksheet endpoint with numeric lessonId (backward compatibility):`);
        print(`GET /generate-worksheet/?lesson_id=${sampleLesson.lessonId}`);
        print("");
    }
    
    print(`// Test search-lessons endpoint:`);
    print(`GET /search-lessons/?query=${sampleLesson._id}`);
    print(`GET /search-lessons/?query=${sampleLesson.title || 'lesson'}`);
    print("");
    
    print(`// Test lesson-details endpoint:`);
    print(`GET /lesson-details/${sampleLesson._id}`);
    print("");
}

// =============================================================================
// PART 4: Collection Schema Analysis
// =============================================================================
print("📊 PART 4: COLLECTION SCHEMA ANALYSIS");
print("=====================================");

const collections = ['lessons', 'lessonmappinggoals', 'lessonplanactivities', 'questions', 'semesters', 'levels', 'subjects', 'stages'];

collections.forEach(collectionName => {
    print(`--- ${collectionName} ---`);
    
    const sample = db.getCollection(collectionName).findOne();
    if (sample) {
        const fields = Object.keys(sample);
        print(`   Sample fields: ${fields.slice(0, 8).join(', ')}${fields.length > 8 ? '...' : ''}`);
        
        // Check for ObjectId fields
        const objectIdFields = [];
        fields.forEach(field => {
            if (sample[field] instanceof ObjectId) {
                objectIdFields.push(field);
            } else if (Array.isArray(sample[field]) && sample[field].length > 0 && sample[field][0] instanceof ObjectId) {
                objectIdFields.push(`${field}[]`);
            }
        });
        
        if (objectIdFields.length > 0) {
            print(`   ObjectId fields: ${objectIdFields.join(', ')}`);
        }
    } else {
        print(`   No documents found`);
    }
});

print("");
print("🎯 SCHEMA UPDATE VERIFICATION COMPLETE!");
print("======================================");
print("");
print("📝 Summary of Changes:");
print("- Lesson search now supports both ObjectId (_id) and numeric lessonId");
print("- Goals search uses ObjectId references instead of numeric goalId");
print("- Activities search uses lesson ObjectId reference");
print("- Questions search uses lesson and goal ObjectId references");
print("- Added new API endpoints for searching and detailed lesson info");
print("");
print("⚠️  Important Notes:");
print("- The questions collection may need schema updates to use ObjectId refs");
print("- Activities.goals field may need to store ObjectIds instead of comma-separated numbers");
print("- Test the API endpoints with both ObjectId and lessonId values");
