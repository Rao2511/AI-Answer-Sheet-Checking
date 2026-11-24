import io
from typing import List, Union

import fitz  # PyMuPDF
from core.models import PageData


def _get_document(pdf_path_or_bytes: Union[str, bytes]) -> fitz.Document:
    """Helper to open a fitz Document from path or bytes."""
    if isinstance(pdf_path_or_bytes, str):
        return fitz.open(pdf_path_or_bytes)
    elif isinstance(pdf_path_or_bytes, bytes):
        return fitz.open("pdf", pdf_path_or_bytes)
    else:
        raise TypeError("pdf_path_or_bytes must be a string (path) or bytes.")


def render_pdf_pages(
    pdf_path_or_bytes: Union[str, bytes],
    dpi: int = 180,
    enhance_handwriting: bool = True,
    rotation_offset: int = 0,
) -> List[PageData]:
    """
    Renders each PDF page to an optimized high-clarity JPEG image at the specified DPI,
    with automatic handwriting enhancement (stroke darkening & contrast boosting).

    Args:
        pdf_path_or_bytes: File path to the PDF or raw PDF bytes.
        dpi: Target DPI for rendering. Default is 180 (optimal balance between sharpness and speed).
        enhance_handwriting: Whether to run auto-contrast and stroke-sharpening for handwritten ink.
        rotation_offset: Additional rotation in degrees (0, 90, 180, 270) if scan is oriented sideways.

    Returns:
        A list of PageData objects containing the enhanced JPEG bytes and metadata.
    """
    from core.handwriting_ocr import enhance_handwriting_image

    page_data_list = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    try:
        doc = _get_document(pdf_path_or_bytes)
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Apply manual rotation offset if specified
            if rotation_offset != 0:
                page.set_rotation((page.rotation + rotation_offset) % 360)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_bytes = pix.tobytes("jpeg")

            # Apply handwriting stroke darkening & contrast enhancement
            if enhance_handwriting:
                image_bytes = enhance_handwriting_image(image_bytes)

            # Create PageData object (page_number is 1-indexed)
            rect = page.rect
            page_data = PageData(
                page_number=page_num + 1,
                width_pts=rect.width,
                height_pts=rect.height,
                image_bytes=image_bytes
            )
            page_data_list.append(page_data)

    except Exception as e:
        raise RuntimeError(f"Error rendering PDF pages: {e}")
    finally:
        if 'doc' in locals():
            doc.close()

    return page_data_list


def get_pdf_page_count(pdf_path_or_bytes: Union[str, bytes]) -> int:
    """
    Quickly gets the number of pages in a PDF without full rendering.

    Args:
        pdf_path_or_bytes: File path to the PDF or raw PDF bytes.

    Returns:
        The total number of pages in the PDF.
    """
    try:
        doc = _get_document(pdf_path_or_bytes)
        count = len(doc)
    except Exception as e:
        raise RuntimeError(f"Error getting PDF page count: {e}")
    finally:
        if 'doc' in locals():
            doc.close()
    return count


def extract_text_from_pdf(pdf_path_or_bytes: Union[str, bytes]) -> str:
    """
    Extracts raw text from the entire PDF document. Useful for rubric PDFs.

    Args:
        pdf_path_or_bytes: File path to the PDF or raw PDF bytes.

    Returns:
        Extracted text as a single string.
    """
    text_content = []
    try:
        doc = _get_document(pdf_path_or_bytes)
        for page in doc:
            text_content.append(page.get_text())
    except Exception as e:
        raise RuntimeError(f"Error extracting text from PDF: {e}")
    finally:
        if 'doc' in locals():
            doc.close()
            
    return "\n".join(text_content)
