#!/usr/bin/env python3
"""Script để test kết nối database và kiểm tra dữ liệu"""

from app.config.database_configuration import get_database

def test_database():
    print("=== TESTING DATABASE CONNECTION ===\n")
    
    # Kết nối database
    db = get_database()
    client = db.client
    
    # Liệt kê tất cả databases
    print("=== ALL DATABASES ===")
    all_dbs = client.list_database_names()
    for db_name in all_dbs:
        print(f"  - {db_name}")
    
    print(f"\n=== CURRENT DATABASE: {db.name} ===")
    
    # Liệt kê tất cả collections
    collections = db.list_collection_names()
    print(f"Collections in '{db.name}': {collections}")
    
    # Kiểm tra các database khác có collection ly_courses không
    print("\n=== SEARCHING FOR 'ly_courses' IN ALL DATABASES ===")
    for db_name in all_dbs:
        temp_db = client[db_name]
        temp_collections = temp_db.list_collection_names()
        if 'ly_courses' in temp_collections:
            print(f"Found 'ly_courses' in database: {db_name}")
            count = temp_db['ly_courses'].count_documents({})
            print(f"  -> Document count: {count}")
        elif temp_collections:
            print(f"Database '{db_name}' has collections: {temp_collections}")
    
    # Kiểm tra collection ly_courses
    if "ly_courses" in collections:
        collection = db["ly_courses"]
        count = collection.count_documents({})
        print(f"\nTotal documents in 'ly_courses': {count}")
        
        if count > 0:
            # Lấy 5 documents mẫu
            print("\n=== SAMPLE DOCUMENTS ===")
            samples = list(collection.find({}).limit(5))
            for i, doc in enumerate(samples, 1):
                print(f"\nDocument {i}:")
                print(f"  course_name: {doc.get('course_name', 'N/A')}")
                print(f"  sub_topic: {doc.get('sub_topic', 'N/A')}")
                print(f"  class_index: {doc.get('class_index', 'N/A')}")
                print(f"  teacher: {doc.get('teacher', 'N/A')}")
                print(f"  day: {doc.get('day', 'N/A')}")
                print(f"  periods: {doc.get('periods', 'N/A')}")
            
            # Test query với một tên môn cụ thể
            print("\n=== TEST QUERY ===")
            test_course = samples[0].get('course_name') if samples else None
            if test_course:
                print(f"Testing query with course_name: '{test_course}'")
                result = list(collection.find({"course_name": test_course}))
                print(f"Found {len(result)} matching documents")
        else:
            print("\nWARNING: Collection 'ly_courses' is empty!")
    else:
        print("\nERROR: Collection 'ly_courses' not found!")
        print("Available collections:", collections)

if __name__ == "__main__":
    test_database()
