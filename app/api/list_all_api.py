from flask import Blueprint, jsonify, current_app

list_all_bp = Blueprint("list_all", __name__)

@list_all_bp.route("/list-all", methods=["GET"])
def list_all():
    """
    Liệt kê tất cả documents trong collection (dùng cho debug)
    ---
    tags:
      - Debug
    responses:
      200:
        description: Danh sách tất cả documents
        schema:
          type: object
          properties:
            count:
              type: integer
            documents:
              type: array
              items:
                type: object
      500:
        description: Lỗi server
    """
    try:
        collection = current_app.db["ly_courses"]
        all_docs = list(collection.find())
        result = []

        for doc in all_docs:
            doc['_id'] = str(doc['_id'])  # Convert ObjectId -> string
            for key, value in doc.items():
                if hasattr(value, 'tolist'):  # Nếu là numpy array
                    doc[key] = value.tolist()
            result.append(doc)

        return jsonify({"count": len(result), "documents": result})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


