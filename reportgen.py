import markdown
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from bs4 import BeautifulSoup
import os

def convert_markdown_to_pdf(md_file, pdf_file, image_path=None):
    # Read the Markdown content with UTF-8 encoding
    with open(md_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    # Convert Markdown to HTML with extensions
    html_content = markdown.markdown(markdown_content, extensions=['tables'])
    
    # Parse HTML to handle different elements
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get the title from the first h1 element, or use a default
    title = "InterstellarShield Scan Report"

    
    # Create PDF document with metadata
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=50,
        bottomMargin=50,
        title=title,
        author="InterstellarShield",
        subject="Manual Malware Scan Report",
        creator="InterstellarShield Report Generator"
    )
    
    # Create styles with dark mode colors
    styles = getSampleStyleSheet()
    
    # Add a new style for findings labels
    findings_label_style = ParagraphStyle(
        'FindingsLabel',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        leftIndent=20,
        leading=14,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        leftIndent=40,
        leading=14,
        textColor=colors.white
    )

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.white,
        alignment=1  # Center alignment
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.white
    )
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.white,
        leftIndent=20
    )
    instance_style = ParagraphStyle(
        'InstanceStyle',
        parent=styles['Heading4'],
        fontSize=14,
        spaceAfter=6,
        textColor=colors.HexColor('#1abc9c'),
        leftIndent=20,
        leading=16
    )
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        leading=14,
        leftIndent=20,
        bulletIndent=10,
        textColor=colors.white
    )
    
    # Build PDF content
    story = []
    
    # Add image if provided
    if image_path and os.path.exists(image_path):
        try:
            img = Image(image_path)
            aspect = img.imageWidth / img.imageHeight
            if aspect > 1:
                img.drawWidth = 6 * inch
                img.drawHeight = 6 * inch / aspect
            else:
                img.drawHeight = 6 * inch
                img.drawWidth = 6 * inch * aspect
            story.append(img)
            story.append(Spacer(1, 24))
        except Exception as e:
            print(f"Warning: Could not add image: {e}")

    # Add title
    title_element = soup.find('h1')
    if title_element:
        story.append(Paragraph(title_element.text.strip(), title_style))
        story.append(Spacer(1, 12))

    # Add page break
    story.append(PageBreak())
    
    # Add centered scan results header at top of second page
    story.append(Paragraph("Manual ClamAV Scan Results Report", ParagraphStyle(
        'CenteredHeader',
        parent=heading_style,
        alignment=1,  # Center alignment
        spaceAfter=30
    )))

    # Custom canvas to set background and add timestamp
    def set_background(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#263743'))
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        # Add timestamp at bottom of first page only
        if doc.page == 1:
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica', 14)
            timestamp_text = soup.find(string=lambda t: 'Report generated:' in str(t))
            if timestamp_text:
                canvas.drawCentredString(letter[0]/2, 50, timestamp_text.strip())
        
        canvas.restoreState()

    # Skip these elements in the main content processing
    skip_elements = {'Report generated:', 'Manual ClamAV Scan Results Report'}

    content = []
    current_section = []  # Initialize current_section list

    # Process remaining content
    for element in soup.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'li', 'hr']):
        try:
            text = element.text.strip()
            if not text and element.name != 'hr':  # Skip empty elements except for hr
                continue
                
            # Skip the elements we've handled separately
            if any(skip_text in text for skip_text in skip_elements):
                continue
            elif element.name == 'h2':
                # Section headers go directly to story
                if current_section:
                    story.append(KeepTogether(current_section))
                    current_section = []
                story.append(Paragraph(text, heading_style))
                story.append(Spacer(1, 12))
                continue
            elif element.name == 'h3':
                content.append(Paragraph(text, subheading_style))
            elif element.name == 'h4':
                content.append(Paragraph(text, instance_style))
            elif element.name == 'ul':
                for li in element.find_all('li', recursive=False):
                    content.append(Paragraph(f"• {li.text.strip()}", bullet_style))
            elif element.name == 'p':
                # Check if this is a findings label
                if element.find('strong') and 'Findings:' in element.text:
                    content.append(Paragraph('Findings:', findings_label_style))
                    # Add the rest of the text after "Findings:" as normal content
                    findings_text = element.text.replace('Findings:', '').strip()
                    if findings_text and findings_text != "No malware detected.":
                        # Use a red color for detected malware
                        findings_style = ParagraphStyle(
                            'FindingsRed',
                            parent=normal_style,
                            textColor=colors.HexColor('#b01a1a')
                        )
                        # Split the findings text into lines
                        findings_lines = findings_text.split('\n')
                        for line in findings_lines:
                            if line.strip():  # Only process non-empty lines
                                if line.startswith('Please review'):
                                    # Add log path line with slightly different styling
                                    log_style = ParagraphStyle(
                                        'LogPath',
                                        parent=findings_style,
                                        leftIndent=60  # Increased indent for log path
                                    )
                                    content.append(Paragraph(line.strip(), log_style))
                                else:
                                    content.append(Paragraph(line.strip(), findings_style))
                    else:
                        content.append(Paragraph(findings_text, normal_style))
                else:
                    content.append(Paragraph(text, normal_style))
            elif element.name == 'hr':
                # When we hit a horizontal rule, add the current section to story
                if current_section:
                    story.append(KeepTogether(current_section))
                    current_section = []
                story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1abc9c')))
                story.append(Spacer(1, 12))
                continue
            
            # Add spacing
            content.append(Spacer(1, 6))
            
            # Add content to current section
            current_section.extend(content)
            content = []  # Clear content list for next iteration
                
        except Exception as e:
            print(f"Warning: Could not process element {element.name}: {e}")
    
    # Add any remaining section
    if current_section:
        story.append(KeepTogether(current_section))
    
    try:
        # Generate PDF with background
        doc.build(story, onFirstPage=set_background, onLaterPages=set_background)
        print(f"PDF successfully saved as {pdf_file}")
    except Exception as e:
        print(f"Error generating PDF: {e}")

# Example usage
if __name__ == "__main__":
    try:
        convert_markdown_to_pdf(
            './examples/example_scan_report.md',
            './examples/example_scan_report.pdf',
            './img/interstellarshield.png'
        )
    except Exception as e:
        print(f"Fatal error: {e}")

