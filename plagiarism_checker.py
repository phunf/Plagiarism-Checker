import os
from pydoc import text
import re
from socket import timeout
import docx
import PyPDF2
from typing import List, Dict, Union
from difflib import SequenceMatcher
import json
import requests  # Thêm thư viện requests để kiểm tra trực tuyến

class PlagiarismChecker:
    def __init__(self, similarity_threshold: float = 0.7, max_paragraphs: int = 20):
        """
        Khởi tạo trình kiểm tra đạo văn
        
        :param similarity_threshold: Ngưỡng độ tương đồng để cảnh báo đạo văn
        :param max_paragraphs: Số lượng đoạn tối đa để kiểm tra
        """
        self.similarity_threshold = similarity_threshold
        self.max_paragraphs = max_paragraphs
        self.supported_extensions = ['.txt', '.docx', '.pdf']

        # Thiết lập thư mục lưu file
        self.base_dir = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        # Thiết lập API Google (thay thế bằng key của bạn)
        self.google_api_key = "YOUR_GOOGLE_API_KEY"
        self.search_engine_id = "YOUR_SEARCH_ENGINE_ID"
        
    def _read_file(self, file_path: str) -> str:
        """
        Đọc nội dung file với nhiều phương pháp encoding và loại file
        
        :param file_path: Đường dẫn file
        :return: Nội dung file dạng văn bản
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # Xử lý từng loại file
            if file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            
            elif file_ext == '.docx':
                doc = docx.Document(file_path)
                return '\n'.join([paragraph.text for paragraph in doc.paragraphs if paragraph.text])
            
            elif file_ext == '.pdf':
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ''
                    for page in reader.pages:
                        text += page.extract_text() or ''
                return text
            
            else:
                raise ValueError(f"Định dạng file không được hỗ trợ: {file_ext}")
        
        except Exception as e:
            print(f"Lỗi đọc file: {e}")
            return ""

    def _preprocess_text(self, text: str) -> str:
        """
        Xử lý văn bản: chuyển chữ thường, loại bỏ ký tự đặc biệt
        
        :param text: Văn bản đầu vào
        :return: Văn bản đã xử lý
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Chuyển về chữ thường
        text = text.lower()
        
        # Loại bỏ ký tự đặc biệt và khoảng trắng thừa
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        
        return text.strip()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Tính độ tương đồng giữa hai đoạn văn bản
        
        :param text1: Đoạn văn bản thứ nhất
        :param text2: Đoạn văn bản thứ hai
        :return: Độ tương đồng (0.0 - 1.0)
        """
        processed_text1 = self._preprocess_text(text1)
        processed_text2 = self._preprocess_text(text2)
        
        if not processed_text1 or not processed_text2:
            return 0.0
        
        matcher = SequenceMatcher(None, processed_text1, processed_text2)
        return matcher.ratio()
    
    def check_plagiarism_against_uploaded_files(self, file_path: str) -> List[Dict[str, Union[str, float]]]:
        """
        Kiểm tra đạo văn của một tệp so với các tệp đã tải lên trước đó
        
        :param file_path: Đường dẫn tệp cần kiểm tra
        :return: Danh sách các tệp có mức độ đạo văn
        """
        # Kiểm tra định dạng file
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(f"Định dạng file không được hỗ trợ: {file_ext}")
        
        # Đọc nội dung file cần kiểm tra
        current_file_content = self._read_file(file_path)
        
        # Danh sách kết quả đạo văn
        plagiarism_results = []
        
        # Lấy danh sách các tệp đã tải lên trước đó
        uploaded_files = self._get_uploaded_files()
        
        # Chia nội dung file hiện tại thành các đoạn
        current_paragraphs = [p.strip() for p in current_file_content.split('\n\n') if p.strip()]
        current_paragraphs = current_paragraphs[:self.max_paragraphs]
        
        # Kiểm tra từng tệp đã tải lên
        for uploaded_file in uploaded_files:
            if uploaded_file == file_path:
                continue  # Bỏ qua tệp đang kiểm tra
            
            # Đọc nội dung tệp đã tải lên
            uploaded_file_content = self._read_file(uploaded_file)
            uploaded_paragraphs = [p.strip() for p in uploaded_file_content.split('\n\n') if p.strip()]
            
            # Biến lưu mức độ đạo văn
            total_similarity = 0
            matched_paragraphs = 0
            
            # So sánh từng đoạn của file hiện tại với các đoạn file đã tải lên
            for current_para in current_paragraphs:
                for uploaded_para in uploaded_paragraphs:
                    similarity = self._calculate_similarity(current_para, uploaded_para)
                    
                    if similarity > self.similarity_threshold:
                        total_similarity += similarity
                        matched_paragraphs += 1
            
            # Tính % đạo văn
            if matched_paragraphs > 0:
                avg_similarity = (total_similarity / matched_paragraphs) * 100
                
                if avg_similarity > self.plagiarism_threshold:
                    plagiarism_results.append({
                        'file_path': uploaded_file,
                        'plagiarism_percentage': round(avg_similarity, 2),
                        'matched_paragraphs': matched_paragraphs
                    })
        
        # Sắp xếp kết quả theo % đạo văn giảm dần
        plagiarism_results.sort(key=lambda x: x['plagiarism_percentage'], reverse=True)
        
        return plagiarism_results

    def _get_uploaded_files(self) -> List[str]:
        """Lấy danh sách các file đã upload"""
        try:
            if not os.path.exists(self.base_dir):
                return []
                
            files = []
            for filename in os.listdir(self.base_dir):
                if os.path.isfile(os.path.join(self.base_dir, filename)):
                    # Chỉ lấy các file có định dạng được hỗ trợ
                    if any(filename.lower().endswith(ext) for ext in self.supported_extensions):
                        files.append(os.path.join(self.base_dir, filename))
            return files
        except Exception as e:
            print(f"Lỗi khi lấy danh sách file: {str(e)}")
            return []


    def check_internal_plagiarism(self, file_path: str) -> List[Dict[str, Union[str, float]]]:
        """
        Kiểm tra đạo văn trong nội bộ file
        
        :param file_path: Đường dẫn file cần kiểm tra
        :return: Danh sách các đoạn văn bị nghi ngờ đạo văn
        """
        # Kiểm tra định dạng file
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(f"Định dạng file không được hỗ trợ: {file_ext}")
        
        # Đọc nội dung file
        content = self._read_file(file_path)
        
        # Chia văn bản thành các đoạn
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        paragraphs = paragraphs[:self.max_paragraphs]  # Giới hạn số đoạn
        
        internal_plagiarism = []
        
        for i in range(len(paragraphs)):
            for j in range(i+1, len(paragraphs)):
                similarity = self._calculate_similarity(paragraphs[i], paragraphs[j])
                
                if similarity > self.similarity_threshold:
                    internal_plagiarism.append({
                        'paragraph1': paragraphs[i],
                        'paragraph2': paragraphs[j],
                        'similarity': round(similarity * 100, 2)
                    })
        
        return internal_plagiarism

    def check_online_plagiarism(self, file_path: str) -> List[Dict[str, Union[str, float, List[str]]]]:
        """
        Kiểm tra đạo văn từ các nguồn trực tuyến
        
        :param file_path: Đường dẫn file cần kiểm tra
        :return: Danh sách các đoạn văn bị nghi ngờ đạo văn
        """
        # Kiểm tra định dạng file
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_extensions:
            raise ValueError(f"Định dạng file không được hỗ trợ: {file_ext}")
        
        # Đọc nội dung file
        content = self._read_file(file_path)
        
        # Chia văn bản thành các đoạn
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        paragraphs = paragraphs[:self.max_paragraphs]  # Giới hạn số đoạn
        
        online_plagiarism = []
        
        for paragraph in paragraphs:
            # Bỏ qua các đoạn quá ngắn
            if len(paragraph) < 50:
                continue
            
            # Tìm kiếm trên Google
            sources = self._search_google(paragraph)
            
            if sources:
                online_plagiarism.append({
                    'paragraph': paragraph,
                    'sources': sources,
                    'max_similarity': max(sources, key=lambda x: x['similarity'])['similarity']
                })
        
        return online_plagiarism

    def _search_google(self, query: str, num_results: int = 5) -> List[Dict[str, Union[str, float]]]:
        """
        Tìm kiếm văn bản trên Google
        
        :param text: Văn bản cần tìm kiếm
        :param timeout: Thời gian timeout cho request
        :return: Danh sách các nguồn tìm thấy
        """
        try:
            # Giới hạn độ dài query
            query = text[:1000]
            
            # Tạo URL tìm kiếm
            search_url = f"https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.search_engine_id,
                'q': query
            }
            
            # Thực hiện request với timeout
            response = requests.get(
                search_url, 
                params=params,
                timeout=timeout
            )
            
            if response.status_code != 200:
                print(f"Lỗi API Google: {response.status_code}")
                return []
                
            # Parse kết quả JSON
            results = response.json()
            
            if 'items' not in results:
                return []
                
            sources = []
            for item in results['items'][:5]:  # Giới hạn 5 kết quả
                try:
                    # Lấy nội dung từ trang web
                    page_content = self._get_page_content(item['link'])
                    
                    # Tính độ tương đồng
                    similarity = self._calculate_similarity(text, page_content)
                    
                    if similarity > self.similarity_threshold:
                        sources.append({
                            'url': item['link'],
                            'title': item['title'],
                            'snippet': item.get('snippet', ''),
                            'similarity': round(similarity * 100, 2)
                        })
                except Exception as e:
                    print(f"Lỗi khi xử lý kết quả tìm kiếm: {str(e)}")
                    continue
                    
            return sources
            
        except requests.exceptions.Timeout:
            print("Timeout khi tìm kiếm")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Lỗi request: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            print(f"Lỗi parse JSON: {str(e)}")
            return []
        except Exception as e:
            print(f"Lỗi không xác định: {str(e)}")
            return []

    def generate_plagiarism_report(self, file_path: str) -> Dict[str, Union[str, List]]:
        """
        Tạo báo cáo kiểm tra đạo văn đầy đủ
        
        :param file_path: Đường dẫn file cần kiểm tra
        :return: Báo cáo chi tiết về đạo văn
        """
        filename = os.path.basename(file_path)
        
        try:
            internal_results = self.check_internal_plagiarism(file_path)
            online_results = self.check_online_plagiarism(file_path)
            
            return {
                'filename': filename,
                'file_id': hash(file_path),  # Tạo ID duy nhất cho file
                'internal_plagiarism': internal_results,
                'online_plagiarism': online_results,
                'total_paragraphs': len(self._read_file(file_path).split('\n\n'))
            }
        
        except Exception as e:
            return {
                'error': str(e)
            }
