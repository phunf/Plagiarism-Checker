import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import sys
import uuid
import docx
import PyPDF2
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from plagiarism_checker import PlagiarismChecker

app = Flask(__name__)

# Cấu hình cơ sở dữ liệu
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///plagiarism_files.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Giới hạn 50MB

# Tạo thư mục uploads nếu chưa tồn tại
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Khởi tạo cơ sở dữ liệu
db = SQLAlchemy(app)

# Mô hình dữ liệu cho file
class PlagiarismFile(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    internal_plagiarism = db.Column(db.JSON)
    online_plagiarism = db.Column(db.JSON)
    against_results = db.Column(db.JSON)

# Tạo bảng trong cơ sở dữ liệu
with app.app_context():
    db.create_all()

def extract_text_from_file(filepath):
    """Trích xuất văn bản từ các định dạng file khác nhau"""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext == '.txt':
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    
    elif ext == '.docx':
        doc = docx.Document(filepath)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs if paragraph.text])
    
    elif ext == '.pdf':
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text()
            return text
        
    else:
        raise ValueError("Định dạng file không được hỗ trợ")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_plagiarism', methods=['POST'])
def check_plagiarism():
    try:
        # Kiểm tra file upload
        if 'file' not in request.files:
            return jsonify({'error': 'Không có file được tải lên'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Không có file nào được chọn'}), 400
        
        # Kiểm tra định dạng file
        allowed_extensions = {'txt', 'doc', 'docx', 'pdf'}
        if not allowed_file(file.filename, allowed_extensions):
            return jsonify({'error': 'Định dạng file không được hỗ trợ'}), 400

        # Tạo tên file duy nhất
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        
        # Đảm bảo thư mục upload tồn tại
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        try:
            file.save(filepath)
            
            # Trích xuất văn bản
            text = extract_text_from_file(filepath)
            if not text.strip():
                raise ValueError("Không thể trích xuất văn bản từ file")
            
            # Lưu văn bản vào file tạm để kiểm tra
            temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_temp.txt")
            with open(temp_filepath, 'w', encoding='utf-8') as temp_file:
                temp_file.write(text)
            
            # Kiểm tra đạo văn
            checker = PlagiarismChecker()
            internal_results = checker.check_internal_plagiarism(temp_filepath)
            against_results = checker.check_plagiarism_against_uploaded_files(temp_filepath)
            online_results = checker.check_online_plagiarism(temp_filepath)
            
            # Xóa file tạm
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

            # Lưu thông tin file vào cơ sở dữ liệu
            new_file = PlagiarismFile(
                id=file_id, 
                original_filename=filename,
                stored_filename=f"{file_id}_{filename}",
                file_type=os.path.splitext(filename)[1][1:],
                internal_plagiarism=internal_results,
                online_plagiarism=online_results,
                against_results=against_results  # Thêm kết quả so sánh với file đã upload
            )
            
            db.session.add(new_file)
            db.session.commit()
            
            return jsonify({
                'file_id': file_id,
                'filename': filename,
                'internal_plagiarism': internal_results,
                'online_plagiarism': online_results,
                'against_results': against_results,
                'status': 'success'
            })
        
        finally:
            # Cleanup: xóa file gốc sau khi xử lý xong
            if os.path.exists(filepath):
                os.remove(filepath)
                
    except Exception as e:
        # Log lỗi để debug
        print(f"Error in check_plagiarism: {str(e)}")
        return jsonify({
            'error': 'Có lỗi xảy ra khi kiểm tra đạo văn',
            'detail': str(e)
        }), 500

# Hàm kiểm tra định dạng file
def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/save_file/<file_id>', methods=['GET'])
def save_file(file_id):
    file = PlagiarismFile.query.get_or_404(file_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.stored_filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File không tồn tại'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=file.original_filename)

@app.route('/list_files', methods=['GET'])
def list_files():
    files = PlagiarismFile.query.order_by(PlagiarismFile.upload_date.desc()).all()
    file_list = [{
        'id': file.id,
        'filename': file.original_filename,
        'upload_date': file.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
        'file_type': file.file_type
    } for file in files]
    return jsonify(file_list)

if __name__ == '__main__':
    app.run(debug=True)
