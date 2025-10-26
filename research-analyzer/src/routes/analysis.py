import json
import re
from flask import Blueprint, request, jsonify
from docx import Document as DocxDocument # Alias to avoid conflict if any
from PyPDF2 import PdfReader

analysis_bp = Blueprint('analysis', __name__)

def configure_gemini(api_key):
    """Configure Gemini with the provided API key"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # List available models to help debug if needed
        # print("Available models:")
        # for m in genai.list_models():
        #     if 'generateContent' in m.supported_generation_methods:
        #         print(m.name)
        return genai
    except ImportError:
        raise Exception("Google Generative AI library not available. Please install google-generativeai package.")

def extract_text_from_file(file_obj):
    """
    Extracts text content from uploaded files (.docx, .pdf).
    Handles .doc files by raising an error as direct text extraction is complex.
    """
    filename = file_obj.filename
    if filename.lower().endswith('.docx'):
        try:
            doc = DocxDocument(file_obj)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            raise Exception(f"Error extracting text from .docx file: {e}")
    elif filename.lower().endswith('.pdf'):
        try:
            reader = PdfReader(file_obj)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            return text
        except Exception as e:
            raise Exception(f"Error extracting text from .pdf file: {e}")
    elif filename.lower().endswith('.doc'):
        # .doc files are binary and require specific libraries (e.g., antiword, pywin32 on Windows)
        # which are not included by default and can be complex to set up.
        # For this example, we'll indicate that .doc text extraction is not supported directly.
        raise Exception("Text extraction from .doc files is not directly supported. Please convert to .docx or .pdf.")
    else:
        # This case should ideally be caught by the extension check in analyze_document,
        # but as a fallback.
        raise Exception("Unsupported file type for text extraction.")


def analyze_document_with_gemini(document_text, api_key):
    """
    Analyze document using Gemini LLM to extract terms, expressions, and costs
    """
    try:
        # Import and configure Gemini
        genai = configure_gemini(api_key)
        
        # Create the model - using a more recent model name
        # The error suggests 'gemini-pro' might be deprecated or unavailable.
        # 'gemini-1.5-flash-latest' is a common and capable model.
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        # Create the prompt for analysis
        prompt = f"""
        Analyze the following research document and extract the following information in JSON format:

        1. Document-specific terms and their definitions. Prioritize the following terms: "Ui", "IDi", "Identity of Ui", "SCi", "User’s Smart card", "PWi", "Password of Ui", "Sj", "The jth Sensor Node", "SIDj", "Identity of the Sensor Sj", "GWN", "Gateway Node", "SK", "Session Key", "Open channel", "Secure channel", "h(.)", "One way hash Function", "∥", "Message concatenation", "⊕", "XOR operation.". Also, identify any other terms explicitly defined within the document. Exclude common abbreviations that are not defined in the document.

        2. Complex expressions (logical, hashing, cryptographic, etc.). For each expression, extract its name, type, communicational cost (in bits), and computational cost (in milliseconds).
           - **Crucially, populate the `expressions` array with ALL identified expressions and their associated costs.**
           - **Exclude Assignment Operations:** Do not include simple assignment operations (e.g., `X = xP`, `K1 = xQ`, `K2 = kX`, `Y = yP`, `Q = kP`) in this list. Focus on logical, hashing, cryptographic, or other complex operations.
           - **Expression Type:** Accurately categorize the `type` as 'logical' (e.g., XOR operations, boolean logic), 'hashing' (e.g., hash functions), 'cryptographic' (e.g., encryption, scalar multiplication, addition), or 'other' based on the expression's nature.
           - **Communicational Cost:**
             - If the document explicitly states a communicational cost (e.g., "requires X bits"), use that value.
             - If no explicit cost is mentioned in the document, use a default of "8 bits".
           - **Computational Cost:**
             - **Priority 1: Document Explicit Costs:** If the document explicitly states a computational cost for an operation (e.g., "Hash Function costs 0.0023 ms"), use that value.
             - **Priority 2: Predefined Costs:** If no explicit cost is found in the document, check if the expression matches one of the following predefined operations and use its associated cost:
               - Hash Function (TH): 0.0023ms
               - Elliptic Curve Scalar Multiplication (TM): 2.226ms
               - Elliptic Curve Addition (TA): 0.0288ms
               - Symmetric Encryption (TS): 0.0046ms
               - Modular Exponentiation (TE): 3.85ms
               - Modular Multiplication (TMM): 0.0147ms
               - Biometric Key Processing (TBio): 63.075ms
               - Extracting a Random Number (TExR): 2.011ms
               - Vector Addition Modulo (Tam): 2ms
               - Matrix Multiplication Modulo (Tmm): 4ms
             - **Priority 3: Default Cost:** If neither an explicit document cost nor a matching predefined operation is found, use a default computational cost of "1ms".
           - Look for explicit mentions of costs using keywords like "cost", "takes", "requires", "ms", "bits".
           - Extract the exact cost value and unit as found in the text.
        3. Analyze the overall project proposal to determine its total communicational cost and total computational cost. This should be a high-level assessment of the proposal's resource requirements, synthesizing information from the document.
           - If the document provides a summary of total costs (e.g., "The total communication cost is X bits", "The overall computation will take Y ms"), use those values.
           - If no explicit summary is found, provide a conservative estimate based on the most significant components identified in section 2, clearly stating that it's an estimate.

        Document text:
        {document_text}

        Please respond with a valid JSON object in the following format:
        {{
            "terms": [
                {{
                    "term": "term name",
                    "description": "term description"
                }}
            ],
            "expressions": [
                {{
                    "expression": "expression name",
                    "type": "logical/hashing/cryptographic/other",
                    "communicational_cost": "cost in bits", 
                    "computational_cost": "cost in ms" 
                }}
            ],
            "overall_costs": {{
                "total_communicational_cost": "total bits", 
                "total_computational_cost": "total ms" 
            }}
        }}

        Ensure the response is valid JSON only, no additional text.
        """
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Try to parse as JSON
        try:
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return result
            else:
                raise ValueError("Could not extract valid JSON from Gemini response")
                
    except Exception as e:
        raise Exception(f"Error analyzing document with Gemini: {str(e)}")

@analysis_bp.route('/analyze', methods=['POST'])
def analyze_document():
    """
    Endpoint to analyze uploaded document
    """
    try:
        # Get the uploaded file and API key
        if 'document' not in request.files:
            return jsonify({'error': 'No document file provided'}), 400
        
        if 'api_key' not in request.form:
            return jsonify({'error': 'No API key provided'}), 400
        
        file = request.files['document']
        api_key = request.form['api_key']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check for allowed file extensions
        allowed_extensions = ('.doc', '.docx', '.pdf')
        if not file.filename.lower().endswith(allowed_extensions):
            return jsonify({'error': f'Unsupported file type. Only {", ".join(allowed_extensions)} files are allowed.'}), 400
        
        # Extract document content based on file type
        document_text = extract_text_from_file(file)
        
        if not document_text.strip():
            return jsonify({'error': 'Document is empty or could not be read'}), 400
        
        # Analyze the document with Gemini
        result = analyze_document_with_gemini(document_text, api_key)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({'status': 'healthy', 'service': 'research-analyzer'})
