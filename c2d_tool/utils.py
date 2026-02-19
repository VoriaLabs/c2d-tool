import uuid

def generate_uuid():
    """Generate a UUID string wrapped in braces, matching C2D format."""
    return f"{{{str(uuid.uuid4())}}}"
