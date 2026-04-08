import pytest
from unittest.mock import MagicMock

# Sample OCR text mimicking real eGujCop 300-DPI output from fir_023.pdf
# Uses the layout patterns the parser's regexes expect:
# - "FIRN <digits>" for FIR number with "0. 010" continuation
# - "1 08151110 <district> Polic <station>" row-1 header
# - "305(a),331(4),54" comma-separated sections
# - "(a) Name <complainant>" anchor
# - Gujarati stolen property with "કુલ રૂ." total
SAMPLE_OCR_TEXT = """1 08151110 અમદાવાદગ્રા Polic સાણંદ  Ye 20 FIRN 11192050250
t મ્ય e Station ar 25
0. 010 (તારીખ 25/01/2025)

ભારતીય ન્યાય સંહિતા 2023 – 305(a),331(4),54

(a) Name દિનાબેન રમેશભાઈ પટેલ Father રમેશભાઈ કાન્તિભાઈ પટેલ
(b) Age 45

ચોરાયેલ મિલકતની વિગત:
સોનાના દાગીના રૂ.1,25,000
રોકડ રકમ રૂ.50,000
એક Samsung Galaxy રૂ.3,500
કુલ રૂ.1,78,500

હકીકત:
તા. 24/01/2025 ના રોજ રાત્રે 11:30 વાગ્યે ફરિયાદી દિનાબેન પોતાના ઘરે
સૂતા હતા ત્યારે અજાણ્યા ઈસમો ઘરમાં પ્રવેશ કરી સોનાના દાગીના, રોકડ રકમ
અને મોબાઈલ ફોન ચોરી કરી ફરાર થયા હતા.

I.O. PI R.K. Sharma, સાણંદ Police Station
"""


@pytest.fixture
def sample_ocr_text():
    """Return sample OCR text from fir_023.pdf for testing."""
    return SAMPLE_OCR_TEXT


@pytest.fixture
def mock_db_connection():
    """Return a mock database connection for testing."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn
