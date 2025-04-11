from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import tempfile
import json
import zipfile
from pathlib import Path
import time

from rag import SimpleRAG
from generate import generate_paper_in_sections, Config

app = FastAPI(
    title="Research Paper Analysis API",
    description="API for analyzing research papers using RAG (Retrieval Augmented Generation) and generating research papers",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG system
google_api_key = os.environ.get("GOOGLE_API_KEY", "AIzaSyAb0h0btQBSzpwInYUhy2YZA9k7U2Zc510")
rag_system = SimpleRAG(google_api_key)

# Initialize paper generator config
paper_config = Config()

# Create temp directory for file uploads
UPLOAD_DIR = tempfile.mkdtemp()

# Create output directory for generated papers
OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class Question(BaseModel):
    query: str
    use_web_search: bool = True

class SummaryResponse(BaseModel):
    message: str
    summary: Optional[Dict[str, Any]] = None

class PaperGenerationRequest(BaseModel):
    topic: str
    details: Optional[str] = None
    paper_type: Optional[int] = 1  # 1: Research, 2: Survey, 3: Methodology, 4: Case Study

class PaperGenerationResponse(BaseModel):
    message: str
    paper_sections: Optional[Dict[str, Any]] = None
    latex_file: Optional[str] = None
    zip_file: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None

@app.post("/upload", response_model=SummaryResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a research paper (PDF, DOCX, or TXT) for analysis.
    """
    try:
        # Validate file extension
        allowed_extensions = ['.pdf', '.docx', '.txt', '.md']
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )

        # Save file temporarily
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Process file with RAG system
        rag_system.add_document(file_path)

        # Clean up
        os.remove(file_path)

        return {
            "message": f"Successfully processed {file.filename}",
            "summary": rag_system.current_summary if rag_system.current_summary else None
        }
    except Exception as e:
        # Clean up file if it exists
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask", response_model=Dict[str, Any])
async def ask_question(question: Question):
    """
    Ask a question about the uploaded research paper.
    """
    if not rag_system.current_document:
        raise HTTPException(
            status_code=400,
            detail="No document loaded. Please upload a document first."
        )

    result = rag_system.answer_question(
        query=question.query,
        use_web_search=question.use_web_search
    )
    return result

@app.get("/summary")
async def get_summary():
    """
    Get the summary of the currently loaded research paper.
    """
    if not rag_system.current_document:
        raise HTTPException(
            status_code=400,
            detail="No document loaded. Please upload a document first."
        )

    if not rag_system.current_summary:
        rag_system.current_summary = rag_system.summarize_paper(content=rag_system.current_document)

    return {
        "file_name": rag_system.current_file_name,
        "summary": rag_system.current_summary
    }

@app.post("/save-summary")
async def save_summary():
    """
    Save the current paper summary as a DOCX file and return it.
    """
    if not rag_system.current_document or not rag_system.current_summary:
        raise HTTPException(
            status_code=400,
            detail="No document summary available. Please upload a document and generate a summary first."
        )

    # Generate output filename
    base_name = os.path.splitext(rag_system.current_file_name)[0]
    output_path = os.path.join(UPLOAD_DIR, f"{base_name}_summary.docx")

    # Save summary
    rag_system.save_summary_as_docx(output_path)

    # Return file
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{base_name}_summary.docx"
    )

@app.get("/current-file")
async def get_current_file():
    """
    Get information about the currently loaded file.
    """
    return {
        "file_name": rag_system.current_file_name,
        "has_summary": rag_system.current_summary is not None
    }

# New endpoints for paper generation

@app.post("/generate-paper", response_model=PaperGenerationResponse)
async def generate_paper(request: PaperGenerationRequest):
    """
    Generate a research paper based on the provided topic and details.
    """
    print(f"Received paper generation request for topic: {request.topic}")
    try:
        # Prepare paper details based on paper type
        paper_details = request.details + "\n\n" if request.details else "\n\n"  

        if request.paper_type == 1:
            paper_details += "Paper Type: This should be a research paper with empirical experiments, results, and analysis."
        elif request.paper_type == 2:
            paper_details += "Paper Type: This should be a comprehensive survey/review paper that analyzes and synthesizes existing literature."
        elif request.paper_type == 3:
            paper_details += "Paper Type: This should be a methodology paper focusing on a novel method or algorithm with theoretical foundations."
        elif request.paper_type == 4:
            paper_details += "Paper Type: This should be a case study paper demonstrating application in a specific domain with practical insights."

        # Make sure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Output directory: {OUTPUT_DIR}")

        # Generate the paper
        print("Starting paper generation...")
        result = generate_paper_in_sections(request.topic, paper_details)        
        print("Paper generation completed")

        if not result:
            print("Error: No result returned from paper generation")
            raise HTTPException(status_code=500, detail="Failed to generate paper")

        # Get the paths of the generated files
        safe_title = "".join(c if c.isalnum() else "_" for c in result['title'][:40])
        latex_filename = f"{safe_title}.tex"
        zip_filename = f"{safe_title}_package.zip"
        
        latex_file_path = os.path.join(OUTPUT_DIR, latex_filename)
        zip_file_path = os.path.join(OUTPUT_DIR, zip_filename)
        
        print(f"LaTeX file: {latex_file_path}, exists: {os.path.exists(latex_file_path)}")
        print(f"ZIP file: {zip_file_path}, exists: {os.path.exists(zip_file_path)}")

        response = {
            "message": "Paper generated successfully",
            "paper_sections": result,
            "latex_file": latex_filename if os.path.exists(latex_file_path) else None,    
            "zip_file": zip_filename if os.path.exists(zip_file_path) else None
        }
        print(f"API Response: {response}")
        return response
    except Exception as e:
        print(f"Error in generate_paper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-paper/{filename}")
async def download_paper(filename: str):
    """
    Download a generated paper file (LaTeX or ZIP).
    """
    # Sanitize filename to prevent directory traversal attacks
    sanitized_filename = os.path.basename(filename)
    file_path = os.path.join(OUTPUT_DIR, sanitized_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {sanitized_filename}")

    # Determine content type based on file extension
    content_type = "application/octet-stream"
    if sanitized_filename.endswith(".tex"):
        content_type = "text/x-tex"
    elif sanitized_filename.endswith(".zip"):
        content_type = "application/zip"

    return FileResponse(
        file_path,
        media_type=content_type,
        filename=sanitized_filename
    )

@app.get("/list-papers")
async def list_papers():
    """
    List all generated papers.
    """
    try:
        # Make sure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        files = []
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith((".tex", ".zip")):
                file_path = os.path.join(OUTPUT_DIR, filename)
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(file_path),
                    "created": os.path.getctime(file_path),
                    "type": "LaTeX" if filename.endswith(".tex") else "ZIP"      
                })

        return {"papers": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update-config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update the paper generator configuration.
    """
    try:
        config = paper_config.config.copy()
        
        if request.api_key is not None:
            config["api_key"] = request.api_key
        
        if request.model is not None:
            config["model"] = request.model
        
        if request.temperature is not None:
            config["temperature"] = request.temperature
        
        if request.max_output_tokens is not None:
            config["max_output_tokens"] = request.max_output_tokens
        
        paper_config.save_config(config)
        
        return {"message": "Configuration updated successfully", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-config")
async def get_config():
    """
    Get the current paper generator configuration.
    """
    try:
        # Return a safe version of the config (without API key)
        safe_config = paper_config.config.copy()
        if "api_key" in safe_config:
            safe_config["api_key"] = "********" if safe_config["api_key"] else ""
        
        return {"config": safe_config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 