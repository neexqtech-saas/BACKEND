"""
OCR Service for Business Card Extraction
Uses EasyOCR for text extraction (no external software required)
"""
import re
from typing import Dict, Optional, List
import json

# Try EasyOCR first (easier, no external dependencies)
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    reader = None  # Will be initialized on first use
except ImportError:
    EASYOCR_AVAILABLE = False
    easyocr = None

# Fallback to Tesseract if EasyOCR not available
try:
    import pytesseract
    from PIL import Image
    import os
    import platform
    
    # Auto-configure Tesseract path for Windows
    if platform.system() == 'Windows':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        
        if not hasattr(pytesseract.pytesseract, 'tesseract_cmd') or not pytesseract.pytesseract.tesseract_cmd:
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
    
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None
    Image = None

OCR_AVAILABLE = EASYOCR_AVAILABLE or TESSERACT_AVAILABLE


class BusinessCardOCRService:
    """
    Service to extract contact information from business card images using OCR
    Uses EasyOCR (preferred) or Tesseract (fallback)
    """
    
    def __init__(self):
        # Common patterns for extraction
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        # Improved phone pattern - matches various formats
        self.phone_pattern = re.compile(
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}(?:[-.\s]?\d{1,9})?'
        )
        # Alternative pattern for Indian phone numbers (10 digits)
        self.phone_pattern_indian = re.compile(
            r'(?:\+91[-.\s]?)?[6-9]\d{9}'
        )
        # Pattern for any sequence of 7+ digits
        self.phone_pattern_simple = re.compile(
            r'\b\d{7,15}\b'
        )
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?'
        )
        self.linkedin_pattern = re.compile(
            r'(?:linkedin\.com/in/|linkedin\.com/company/)[\w-]+',
            re.IGNORECASE
        )
        self.instagram_pattern = re.compile(
            r'(?:instagram\.com/|@)[\w.]+',
            re.IGNORECASE
        )
        self.facebook_pattern = re.compile(
            r'(?:facebook\.com/|fb\.com/)[\w.]+',
            re.IGNORECASE
        )
        self.whatsapp_pattern = re.compile(
            r'(?:whatsapp|wa\.me)[:\s]?\+?\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            re.IGNORECASE
        )
        self.pincode_pattern = re.compile(
            r'\b\d{5,6}(?:-\d{4})?\b'
        )
        
        # Initialize EasyOCR reader if available (lazy loading)
        global reader
        if EASYOCR_AVAILABLE and reader is None:
            try:
                reader = easyocr.Reader(['en'], gpu=False)  # Use CPU mode
            except Exception as e:
                print(f"Warning: EasyOCR initialization failed: {e}")
    
    def extract_text_from_image(self, image_file) -> str:
        """
        Extract raw text from image using EasyOCR (preferred) or Tesseract (fallback)
        """
        global OCR_AVAILABLE, EASYOCR_AVAILABLE, TESSERACT_AVAILABLE, reader
        
        # Runtime check for EasyOCR
        if not EASYOCR_AVAILABLE:
            try:
                import easyocr as ec
                global reader
                reader = ec.Reader(['en'], gpu=False)
                EASYOCR_AVAILABLE = True
                OCR_AVAILABLE = True
            except ImportError:
                pass
        
        # Runtime check for Tesseract
        if not TESSERACT_AVAILABLE:
            try:
                import pytesseract as pt
                from PIL import Image as Img
                import os
                import platform
                
                if platform.system() == 'Windows':
                    possible_paths = [
                        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
                    ]
                    
                    if not hasattr(pt.pytesseract, 'tesseract_cmd') or not pt.pytesseract.tesseract_cmd:
                        for path in possible_paths:
                            if os.path.exists(path):
                                pt.pytesseract.tesseract_cmd = path
                                break
                
                global pytesseract, Image
                pytesseract = pt
                Image = Img
                TESSERACT_AVAILABLE = True
                OCR_AVAILABLE = True
            except ImportError:
                pass
        
        if not OCR_AVAILABLE:
            raise Exception(
                "OCR functionality is not available. Please install one of the following:\n"
                "1. EasyOCR (recommended): pip install easyocr\n"
                "2. Tesseract: pip install pytesseract pillow and install Tesseract OCR software"
            )
        
        try:
            # Try EasyOCR first (better accuracy, no external dependencies)
            if EASYOCR_AVAILABLE and reader is not None:
                try:
                    # Read image file
                    import numpy as np
                    from PIL import Image as PILImage
                    
                    # Open and convert image
                    img = PILImage.open(image_file)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Convert to numpy array
                    img_array = np.array(img)
                    
                    # Extract text using EasyOCR
                    results = reader.readtext(img_array)
                    
                    # Combine all detected text
                    text_lines = [result[1] for result in results]
                    text = '\n'.join(text_lines)
                    
                    return text
                except Exception as e:
                    print(f"EasyOCR extraction failed: {e}, falling back to Tesseract")
                    # Fall through to Tesseract
            
            # Fallback to Tesseract
            if TESSERACT_AVAILABLE:
                # Open image
                image = Image.open(image_file)
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Perform OCR
                text = pytesseract.image_to_string(image, lang='eng')
                return text
            else:
                raise Exception("No OCR engine available")
                
        except pytesseract.TesseractNotFoundError if TESSERACT_AVAILABLE else Exception:
            raise Exception(
                "Tesseract OCR is not installed or not found in PATH. "
                "Please install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki "
                "or use EasyOCR instead: pip install easyocr"
            )
        except Exception as e:
            error_msg = str(e)
            if "tesseract" in error_msg.lower() or "not found" in error_msg.lower():
                raise Exception(
                    f"OCR error: {error_msg}. "
                    "Please install EasyOCR: pip install easyocr (recommended) "
                    "or Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki"
                )
            raise Exception(f"OCR extraction failed: {error_msg}")
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text"""
        emails = self.email_pattern.findall(text)
        return list(set(emails))  # Remove duplicates
    
    def extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers from text"""
        phones = []
        
        # Try Indian phone pattern first (10 digits starting with 6-9)
        indian_phones = self.phone_pattern_indian.findall(text)
        for phone in indian_phones:
            cleaned = re.sub(r'[-.\s()]', '', phone)
            if len(cleaned) >= 10:
                phones.append(cleaned)
        
        # Try general phone pattern
        general_phones = self.phone_pattern.findall(text)
        for phone in general_phones:
            if isinstance(phone, tuple):
                phone = ''.join(phone)
            cleaned = re.sub(r'[-.\s()]', '', str(phone))
            if len(cleaned) >= 7 and cleaned not in phones:
                phones.append(cleaned)
        
        # Try simple pattern (any 7-15 digit sequence)
        simple_phones = self.phone_pattern_simple.findall(text)
        for phone in simple_phones:
            cleaned = re.sub(r'[-.\s()]', '', phone)
            # Filter out pincodes (5-6 digits) and very long numbers
            if 7 <= len(cleaned) <= 15 and cleaned not in phones:
                # Skip if it looks like a pincode (5-6 digits at end of line)
                if len(cleaned) <= 6:
                    continue
                phones.append(cleaned)
        
        # Remove duplicates and sort by length (prefer longer numbers)
        phones = list(set(phones))
        phones.sort(key=len, reverse=True)
        
        return phones
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text"""
        urls = self.url_pattern.findall(text)
        return list(set(urls))
    
    def extract_social_links(self, text: str) -> Dict[str, str]:
        """Extract social media links from text"""
        social_links = {}
        
        # LinkedIn
        linkedin_matches = self.linkedin_pattern.findall(text)
        if linkedin_matches:
            link = linkedin_matches[0]
            if not link.startswith('http'):
                link = f"https://{link}"
            social_links['linkedin'] = link
        
        # Instagram
        instagram_matches = self.instagram_pattern.findall(text)
        if instagram_matches:
            link = instagram_matches[0]
            if link.startswith('@'):
                link = link[1:]
            if not link.startswith('http'):
                link = f"https://instagram.com/{link}"
            elif not link.startswith('http'):
                link = f"https://{link}"
            social_links['instagram'] = link
        
        # Facebook
        facebook_matches = self.facebook_pattern.findall(text)
        if facebook_matches:
            link = facebook_matches[0]
            if not link.startswith('http'):
                link = f"https://{link}"
            social_links['facebook'] = link
        
        # WhatsApp
        whatsapp_matches = self.whatsapp_pattern.findall(text)
        if whatsapp_matches:
            phone = re.sub(r'[^\d+]', '', whatsapp_matches[0])
            social_links['whatsapp'] = phone
        
        return social_links
    
    def extract_address_components(self, text: str) -> Dict[str, Optional[str]]:
        """Extract address components (state, city, country, pincode)"""
        address_data = {
            'state': None,
            'city': None,
            'country': None,
            'pincode': None
        }
        
        # Extract pincode
        pincodes = self.pincode_pattern.findall(text)
        if pincodes:
            address_data['pincode'] = pincodes[0]
        
        # Common Indian states
        indian_states = [
            'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
            'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
            'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
            'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
            'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
            'Uttar Pradesh', 'Uttarakhand', 'West Bengal'
        ]
        
        # Try to find state
        for state in indian_states:
            if state.lower() in text.lower():
                address_data['state'] = state
                break
        
        # Common Indian cities (sample list)
        indian_cities = [
            'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai', 'Kolkata',
            'Pune', 'Ahmedabad', 'Jaipur', 'Surat', 'Lucknow', 'Kanpur',
            'Nagpur', 'Indore', 'Thane', 'Bhopal', 'Visakhapatnam', 'Patna',
            'Vadodara', 'Ghaziabad', 'Ludhiana', 'Agra', 'Nashik', 'Faridabad'
        ]
        
        # Try to find city
        for city in indian_cities:
            if city.lower() in text.lower():
                address_data['city'] = city
                break
        
        # Default country to India if Indian state/city found
        if address_data['state'] or address_data['city']:
            address_data['country'] = 'India'
        
        return address_data
    
    def extract_name_and_title(self, text_lines: List[str]) -> Dict[str, Optional[str]]:
        """Extract name and job title from text lines"""
        result = {
            'full_name': None,
            'job_title': None,
            'department': None
        }
        
        if not text_lines:
            return result
        
        # Common job titles
        job_titles = [
            'CEO', 'CTO', 'CFO', 'COO', 'CMO', 'Director', 'Manager',
            'President', 'Vice President', 'VP', 'Head', 'Lead', 'Senior',
            'Executive', 'Officer', 'Specialist', 'Analyst', 'Engineer',
            'Developer', 'Designer', 'Consultant', 'Advisor', 'Coordinator'
        ]
        
        # Common departments
        departments = [
            'Sales', 'Marketing', 'IT', 'HR', 'Finance', 'Operations',
            'Engineering', 'Product', 'Customer Service', 'Support',
            'Business Development', 'Research', 'Development', 'R&D'
        ]
        
        # First line is usually the name
        if text_lines:
            first_line = text_lines[0].strip()
            # Check if first line contains job title
            has_title = any(title.lower() in first_line.lower() for title in job_titles)
            
            if not has_title and len(first_line.split()) <= 4:
                result['full_name'] = first_line
            else:
                # Split name and title
                parts = first_line.split(',')
                if len(parts) >= 2:
                    result['full_name'] = parts[0].strip()
                    result['job_title'] = parts[1].strip()
                else:
                    result['full_name'] = first_line
        
        # Look for job title in subsequent lines
        for line in text_lines[1:5]:  # Check first 5 lines
            line_lower = line.lower()
            for title in job_titles:
                if title.lower() in line_lower:
                    if not result['job_title']:
                        result['job_title'] = line.strip()
                    break
            
            for dept in departments:
                if dept.lower() in line_lower:
                    if not result['department']:
                        result['department'] = dept
                    break
        
        return result
    
    def extract_contact_info(self, image_file) -> Dict:
        """
        Main method to extract all contact information from business card image
        Returns a dictionary with all extracted fields
        """
        try:
            # Extract raw text
            raw_text = self.extract_text_from_image(image_file)
            
            if not raw_text or len(raw_text.strip()) < 10:
                return {
                    'success': False,
                    'error': 'Could not extract sufficient text from image',
                    'raw_text': raw_text
                }
            
            # Split into lines for better processing
            text_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            # Initialize result
            result = {
                'success': True,
                'full_name': None,
                'company_name': None,
                'job_title': None,
                'department': None,
                'mobile_number': None,
                'alternate_phone': None,
                'office_landline': None,
                'fax_number': None,
                'email_address': None,
                'alternate_email': None,
                'full_address': None,
                'state': None,
                'city': None,
                'country': None,
                'pincode': None,
                'whatsapp_number': None,
                'additional_notes': None
            }
            
            # Extract name and title
            name_title = self.extract_name_and_title(text_lines)
            result['full_name'] = name_title.get('full_name')
            result['job_title'] = name_title.get('job_title')
            result['department'] = name_title.get('department')
            
            # Extract emails
            emails = self.extract_emails(raw_text)
            if emails:
                result['email_address'] = emails[0]
                if len(emails) > 1:
                    result['alternate_email'] = emails[1]
            
            # Extract phone numbers
            phones = self.extract_phones(raw_text)
            if phones:
                result['mobile_number'] = phones[0]
                if len(phones) > 1:
                    result['alternate_phone'] = phones[1]
                if len(phones) > 2:
                    result['office_landline'] = phones[2]
            
            # Extract social links (only whatsapp now)
            social_links = self.extract_social_links(raw_text)
            result['whatsapp_number'] = social_links.get('whatsapp')
            
            # Extract address components
            address_data = self.extract_address_components(raw_text)
            result['state'] = address_data.get('state')
            result['city'] = address_data.get('city')
            result['country'] = address_data.get('country')
            result['pincode'] = address_data.get('pincode')
            
            # Try to extract company name (usually in second or third line)
            for line in text_lines[1:4]:
                line_lower = line.lower()
                # Skip if it's an email, phone, or URL
                if '@' in line or any(char.isdigit() for char in line) and len([c for c in line if c.isdigit()]) > 5:
                    continue
                # Skip if it's a job title
                if any(title.lower() in line_lower for title in ['manager', 'director', 'engineer', 'officer']):
                    continue
                if not result['company_name'] and len(line) > 3:
                    result['company_name'] = line.strip()
                    break
            
            # Extract full address (lines that look like addresses)
            address_lines = []
            for line in text_lines:
                line_lower = line.lower()
                # Skip if it's name, email, phone, or URL
                if '@' in line or any(char.isdigit() for char in line) and len([c for c in line if c.isdigit()]) > 8:
                    continue
                if any(word in line_lower for word in ['www', 'http', '.com', '.in', '.org']):
                    continue
                # Look for address indicators
                if any(word in line_lower for word in ['street', 'road', 'avenue', 'lane', 'nagar', 'colony', 'sector']):
                    address_lines.append(line)
                elif address_data.get('city') and address_data['city'].lower() in line_lower:
                    address_lines.append(line)
                elif address_data.get('state') and address_data['state'].lower() in line_lower:
                    address_lines.append(line)
                elif address_data.get('pincode') and address_data['pincode'] in line:
                    address_lines.append(line)
            
            if address_lines:
                result['full_address'] = ', '.join(address_lines)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'raw_text': None
            }
