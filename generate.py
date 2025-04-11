import os
import zipfile
import json
import time
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.chains import LLMChain

# =============================
# ⚙️ Configuration
# =============================

# Configuration class to manage settings
class Config:
    def __init__(self):
        self.config_file = "config.json"
        self.default_config = {
            "api_key": "AIzaSyAb0h0btQBSzpwInYUhy2YZA9k7U2Zc510",  # Empty by default for security
            "model": "gemini-2.0-flash",  # Using pro model for better quality
            "temperature": 0.2,  # Slightly higher for more creative but still focused content
            "max_output_tokens": 100000,  # Increased for more comprehensive papers
            "output_dir": "output",
            "ieee_template_dir": "ieee_templates"
        }
        self.config = self.load_config()
        
    def load_config(self):
        """Load configuration from file or create default"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Update with any new fields from default config
                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except json.JSONDecodeError:
                print("⚠️ Invalid config file. Using defaults.")
                return self.default_config.copy()
        else:
            # Create default config file
            self.save_config(self.default_config)
            return self.default_config.copy()
    
    def save_config(self, config):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
    
    def get_api_key(self):
        """Get API key from config or environment"""
        # First check environment variable
        if "GOOGLE_API_KEY" in os.environ:
            return os.environ["GOOGLE_API_KEY"]
        
        # Then check config file
        if self.config.get("api_key"):
            return self.config["api_key"]
        
        # If no API key found, prompt user
        api_key = input("Enter your Google API key: ").strip()
        if api_key:
            self.config["api_key"] = api_key
            self.save_config(self.config)
            return api_key
        
        return None
    
    def ensure_output_dir(self):
        """Ensure output directory exists"""
        os.makedirs(self.config["output_dir"], exist_ok=True)
        return self.config["output_dir"]
    
    def ensure_template_dir(self):
        """Ensure IEEE templates directory exists"""
        os.makedirs(self.config["ieee_template_dir"], exist_ok=True)
        return self.config["ieee_template_dir"]

# Global config instance
config = Config()

# =============================
# 📁 Utility: Save LaTeX + ZIP
# =============================

def generate_ieee_template_files():
    """Generate IEEE style files if they don't exist"""
    template_dir = config.ensure_template_dir()
    
    # IEEEtran.cls (simplified version for this example)
    ieee_cls_path = os.path.join(template_dir, "IEEEtran.cls")
    if not os.path.exists(ieee_cls_path):
        # We'd include the full IEEE class file here. Using a placeholder for brevity.
        with open(ieee_cls_path, 'w') as f:
            f.write(r"""% Placeholder for IEEEtran.cls
\ProvidesClass{IEEEtran}
% This would be the full IEEE transaction class file in a real implementation
""")
    
    # Create a bibliography style file
    ieee_bst_path = os.path.join(template_dir, "IEEEtran.bst")
    if not os.path.exists(ieee_bst_path):
        # Again, this would be the full file in practice
        with open(ieee_bst_path, 'w') as f:
            f.write(r"""% Placeholder for IEEEtran.bst
% This would be the full IEEE bibliography style file
""")
    
    return template_dir

def generate_latex_from_text(paper_sections, filename=None):
    """Generate a LaTeX file from structured paper sections"""
    if filename is None:
        # Create a sanitized filename from the title
        safe_title = "".join(c if c.isalnum() else "_" for c in paper_sections['title'][:40])
        filename = os.path.join(config.ensure_output_dir(), f"{safe_title}.tex")
    
    # Generate IEEE template files
    template_dir = generate_ieee_template_files()
    
    # Validate paper sections
    required_sections = ["title", "authors", "abstract", "keywords", 
                         "introduction", "related_work", "background", "methodology", 
                         "experiment_design", "results", "discussion", 
                         "limitations", "future_work", "conclusion", "references"]
    
    for section in required_sections:
        if section not in paper_sections:
            paper_sections[section] = f"[{section.capitalize().replace('_', ' ')} section missing]"
    
    # Extract figures if any
    figures = paper_sections.get("figures", [])
    figure_code = ""
    
    if figures and isinstance(figures, list):
        for i, figure in enumerate(figures):
            if isinstance(figure, dict) and "caption" in figure and "content" in figure:
                figure_code += f"""
\\begin{{figure}}[htbp]
\\centering
% Figure {i+1}
{figure['content']}
\\caption{{{figure['caption']}}}
\\label{{fig:{i+1}}}
\\end{{figure}}
"""
    
    # Create affiliations for multiple authors
    authors_text = paper_sections['authors'].strip()
    author_list = [author.strip() for author in authors_text.split(",")]
    
    authors_latex = ""
    for i, author in enumerate(author_list):
        if i == 0:
            authors_latex += f"{author}\\IEEEauthorrefmark{{1}}"
        else:
            authors_latex += f", {author}\\IEEEauthorrefmark{{{(i % 3) + 1}}}"
    
    affiliations = r"""
\IEEEauthorblockA{\IEEEauthorrefmark{1}Department of Computer Science, University A, Country\\
\IEEEauthorrefmark{2}AI Research Institute, University B, Country\\
\IEEEauthorrefmark{3}Department of Electrical Engineering, University C, Country\\
Email: corresponding@author.edu}
"""
    
    latex_content = r"""\documentclass[conference]{IEEEtran}
\usepackage[utf8]{inputenc}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{algorithm}
\usepackage{algpseudocode}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{listings}
\usepackage{tikz}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,      
    urlcolor=cyan,
    pdftitle={""" + paper_sections['title'].strip() + r"""}
}

\lstset{
    basicstyle=\ttfamily\small,
    breaklines=true,
    frame=single,
    numbers=left,
    numberstyle=\tiny,
    showstringspaces=false,
    keywordstyle=\color{blue},
    commentstyle=\color{green!60!black},
    stringstyle=\color{red},
    captionpos=b
}

\title{""" + paper_sections['title'].strip() + r"""}

\author{\IEEEauthorblockN{""" + authors_latex + r"""}
""" + affiliations + r"""}

\begin{document}

\maketitle

\begin{abstract}
""" + paper_sections['abstract'].strip() + r"""
\end{abstract}

\begin{IEEEkeywords}
""" + paper_sections['keywords'].strip() + r"""
\end{IEEEkeywords}

\section{Introduction}
""" + paper_sections['introduction'].strip() + r"""

\section{Related Work}
""" + paper_sections['related_work'].strip() + r"""

\section{Background}
""" + paper_sections['background'].strip() + r"""

\section{Methodology}
""" + paper_sections['methodology'].strip() + r"""

\section{Experiment Design}
""" + paper_sections['experiment_design'].strip() + r"""

\section{Results}
""" + paper_sections['results'].strip() + r"""

\section{Discussion}
""" + paper_sections['discussion'].strip() + r"""

\section{Limitations and Ethical Considerations}
""" + paper_sections['limitations'].strip() + r"""

\section{Future Work}
""" + paper_sections['future_work'].strip() + r"""

\section{Conclusion}
""" + paper_sections['conclusion'].strip() + r"""

""" + figure_code + r"""

\bibliographystyle{IEEEtran}
\begin{thebibliography}{00}
""" + paper_sections['references'].strip() + r"""
\end{thebibliography}

\end{document}
"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        print(f"\n✅ LaTeX saved as: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Error saving LaTeX file: {e}")
        return None

# =============================
# 📦 Utility: Create ZIP
# =============================

def create_zip(latex_file):
    """Create a ZIP file containing the LaTeX document and templates"""
    if not latex_file or not os.path.exists(latex_file):
        print("❌ LaTeX file not found. Cannot create ZIP.")
        return None
    
    # Create a meaningful zip filename based on the LaTeX file
    base_name = os.path.splitext(os.path.basename(latex_file))[0]
    zip_filename = os.path.join(config.ensure_output_dir(), f"{base_name}_package.zip")
    
    try:
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            # Add the main LaTeX file
            zipf.write(latex_file, os.path.basename(latex_file))
            
            # Add IEEE template files
            template_dir = config.config["ieee_template_dir"]
            if os.path.exists(template_dir):
                for template_file in os.listdir(template_dir):
                    file_path = os.path.join(template_dir, template_file)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, template_file)
            
            # Add a README file
            readme_content = f"""# {base_name}

This package contains an IEEE-format LaTeX paper generated on {time.strftime("%Y-%m-%d")}. 

## Contents:
- {os.path.basename(latex_file)}: Main LaTeX document
- IEEEtran.cls: IEEE Transaction class file
- IEEEtran.bst: IEEE bibliography style file

## Compilation:
To compile this document:
1. Ensure you have a LaTeX distribution installed (e.g., TeX Live, MiKTeX)
2. Run: pdflatex {os.path.basename(latex_file)}
3. Run: bibtex {base_name}
4. Run: pdflatex {os.path.basename(latex_file)} (twice for proper references)
"""
            readme_file = os.path.join(config.ensure_output_dir(), "README.md")
            with open(readme_file, 'w') as f:
                f.write(readme_content)
            zipf.write(readme_file, "README.md")
            os.remove(readme_file)  # Clean up
        
        print(f"✅ ZIP package created: {zip_filename}")
        return zip_filename
    except Exception as e:
        print(f"❌ Error creating ZIP file: {e}")
        return None

# =============================
# 🤖 Paper Generator Core
# =============================

def generate_paper_in_sections(topic, details=None):
    """Generate an IEEE research paper by breaking it into sections"""
    print(f"\n🚀 Generating comprehensive paper on topic: {topic}\n")

    api_key = config.get_api_key()
    if not api_key:
        print("❌ Cannot proceed without a valid API key.")
        return None

    # Initialize the Gemini model
    try:
        llm = ChatGoogleGenerativeAI(
            model=config.config["model"],
            temperature=config.config["temperature"],
            max_output_tokens=config.config["max_output_tokens"],
            google_api_key=api_key
        )
    except Exception as e:
        print(f"❌ Error initializing Gemini model: {e}")
        return None
    
    # First generate the overall structure and metadata
    print("📋 Planning paper structure and metadata...")
    
    paper_metadata_schemas = [
        ResponseSchema(name="title", description="A compelling, specific academic title for the research paper (10-15 words)"),
        ResponseSchema(name="authors", description="List of 3-5 fictional authors with realistic academic names"),
        ResponseSchema(name="abstract", description="A comprehensive abstract summarizing the entire paper (250-350 words)"),
        ResponseSchema(name="keywords", description="6-8 specific keywords related to the paper, ordered by relevance"),
        ResponseSchema(name="paper_outline", description="A detailed outline of the paper with main sections and subsections")
    ]
    
    metadata_parser = StructuredOutputParser.from_response_schemas(paper_metadata_schemas)
    metadata_format_instructions = metadata_parser.get_format_instructions()
    
    metadata_template = """
    You are a professional academic researcher with expertise in creating high-quality IEEE format research papers.
    
    TASK: Generate the metadata and detailed outline for a comprehensive research paper on this topic:
    
    TOPIC: {topic}
    {details}
    
    REQUIREMENTS:
    - Create an academic title that is specific, informative, and attention-grabbing
    - Generate 3-5 fictional but realistic author names from diverse institutions
    - Write a comprehensive abstract (250-350 words) that effectively summarizes the entire paper 
    - Include 6-8 specific, technical keywords relevant to the research topic
    - Provide a detailed outline with all main sections and key subsections
    
    INSTRUCTIONS:
    - The paper should follow the structure of high-impact IEEE research papers
    - The abstract should mention methodology, key findings, and implications
    - Don't use generic phrases like "this paper presents" in the title
    
    {format_instructions}
    """
    
    metadata_prompt = PromptTemplate(
        template=metadata_template,
        input_variables=["topic", "details"],
        partial_variables={"format_instructions": metadata_format_instructions}
    )
    
    metadata_chain = LLMChain(llm=llm, prompt=metadata_prompt)
    
    try:
        if details is None:
            details = ""
        metadata_result = metadata_chain.run(topic=topic, details=details)
        paper_metadata = metadata_parser.parse(metadata_result)
        
        # Now generate each paper section individually
        paper_sections = {
            "title": paper_metadata["title"],
            "authors": paper_metadata["authors"],
            "abstract": paper_metadata["abstract"],
            "keywords": paper_metadata["keywords"]
        }
        
        # Define all the detailed sections to generate
        section_definitions = [
            {
                "name": "introduction",
                "title": "Introduction",
                "description": "Comprehensive introduction with problem statement, motivation, research gap, objectives, and paper organization (1000-1500 words)"
            },
            {
                "name": "related_work",
                "title": "Related Work",
                "description": "Thorough review of relevant literature, organized thematically with critical analysis (1200-1800 words)"
            },
            {
                "name": "background",
                "title": "Background",
                "description": "Technical background and theoretical foundations necessary to understand the paper (800-1200 words)"
            },
            {
                "name": "methodology",
                "title": "Methodology",
                "description": "Detailed methodology including algorithms, architectures, frameworks, and implementation details (1500-2000 words)"
            },
            {
                "name": "experiment_design",
                "title": "Experiment Design",
                "description": "Experimental setup, datasets, evaluation metrics, and protocols (800-1200 words)"
            },
            {
                "name": "results",
                "title": "Results",
                "description": "Comprehensive results with analysis, tables, and comparisons to baselines (1000-1500 words)"
            },
            {
                "name": "discussion",
                "title": "Discussion",
                "description": "In-depth discussion of results, implications, and connections to broader research (800-1200 words)"
            },
            {
                "name": "limitations",
                "title": "Limitations and Ethical Considerations",
                "description": "Honest assessment of limitations, potential biases, and ethical considerations (600-800 words)"
            },
            {
                "name": "future_work",
                "title": "Future Work",
                "description": "Concrete directions for future research based on findings (600-800 words)"
            },
            {
                "name": "conclusion",
                "title": "Conclusion",
                "description": "Strong conclusion summarizing contributions and significance (600-800 words)"
            }
        ]
        
        # Generate content for each section
        for section in section_definitions:
            print(f"📝 Generating {section['title']} section...")
            
            section_template = """
            You are a professional academic researcher writing a high-quality IEEE format research paper.
            
            TASK: Write the {section_title} section for a research paper on this topic:
            
            TOPIC: {topic}
            
            PAPER TITLE: {title}
            PAPER ABSTRACT: {abstract}
            PAPER OUTLINE: {outline}
            
            SECTION REQUIREMENTS:
            {section_description}
            
            INSTRUCTIONS:
            - Write in formal academic style with appropriate scholarly tone
            - Include relevant subsections with clear headings
            - Incorporate citations in IEEE format [1], [2], etc.
            - Be technically precise and thorough
            - Avoid vague statements and unsupported claims
            - Include specific details, methodologies, and findings
            - Use academic terminology appropriate for the field
            
            RESPONSE FORMAT:
            Return only the content for this section. Do not include the section heading.
            """
            
            section_prompt = PromptTemplate(
                template=section_template,
                input_variables=["section_title", "section_description", "topic", "title", "abstract", "outline"]
            )
            
            section_chain = LLMChain(llm=llm, prompt=section_prompt)
            section_result = section_chain.run(
                section_title=section["title"],
                section_description=section["description"],
                topic=topic,
                title=paper_metadata["title"],
                abstract=paper_metadata["abstract"],
                outline=paper_metadata["paper_outline"]
            )
            
            paper_sections[section["name"]] = section_result.strip()
        
        # Generate references
        print("📚 Generating references...")
        references_template = """
        You are a professional academic researcher writing a high-quality IEEE format research paper.
        
        TASK: Generate a comprehensive bibliography in IEEE format for a research paper on this topic:
        
        TOPIC: {topic}
        TITLE: {title}
        ABSTRACT: {abstract}
        
        REQUIREMENTS:
        - Create 25-35 realistic, high-quality academic references
        - Include recent papers (last 2-3 years) as well as seminal works
        - References should be from reputable journals, conferences, and books
        - Use proper IEEE citation format
        - Include a diverse set of authors and publications
        - References should directly relate to the paper topic and contents
        - Include top venues in the field (e.g., IEEE/ACM transactions, top conferences)
        
        EXAMPLE IEEE FORMAT:
        [1] A. Author, B. Author, and C. Author, "Title of the paper," Journal Name, vol. 1, no. 2, pp. 123-456, Jan. 2023.
        [2] D. Author and E. Author, "Conference paper title," in Proc. Int. Conf. Name (ACRONYM), City, Country, Year, pp. 789-012.
        [3] F. Author, Book Title. Publisher City, Country: Publisher Name, Year.
        
        RESPONSE FORMAT:
        Return ONLY the formatted bibliography entries without any additional text.
        """
        
        references_prompt = PromptTemplate(
            template=references_template,
            input_variables=["topic", "title", "abstract"]
        )
        
        references_chain = LLMChain(llm=llm, prompt=references_prompt)
        references_result = references_chain.run(
            topic=topic,
            title=paper_metadata["title"],
            abstract=paper_metadata["abstract"]
        )
        
        paper_sections["references"] = references_result.strip()
        
        # Generate LaTeX file and ZIP package
        latex_file = generate_latex_from_text(paper_sections)
        if latex_file:
            zip_path = create_zip(latex_file)
            if zip_path:
                print(f"\n📦 Paper package created successfully at: {zip_path}")
                print(f"📄 LaTeX file available at: {latex_file}")
        
        return paper_sections
    
    except Exception as e:
        print(f"❌ Error generating paper: {e}")
        
        # More robust error handling
        if 'paper_metadata' in locals() and paper_metadata:
            print("\n⚠️ Partial metadata was generated. Attempting to salvage...")
            
            # Create a minimal paper with available metadata
            salvaged_sections = {
                "title": paper_metadata.get("title", topic),
                "authors": paper_metadata.get("authors", "Anonymous Authors"),
                "abstract": paper_metadata.get("abstract", f"Research on {topic}."),
                "keywords": paper_metadata.get("keywords", f"{topic}, research"),
                "introduction": f"This paper explores {topic}. [Content generation failed]",
                "related_work": "[Related work content generation failed]",
                "background": "[Background content generation failed]",
                "methodology": "[Methodology content generation failed]",
                "experiment_design": "[Experiment design content generation failed]",
                "results": "[Results content generation failed]",
                "discussion": "[Discussion content generation failed]",
                "limitations": "[Limitations content generation failed]",
                "future_work": "[Future work content generation failed]",
                "conclusion": "[Conclusion content generation failed]",
                "references": "[1] [References content generation failed]"
            }
            
            # Try to use any sections that might have been generated
            if 'paper_sections' in locals() and paper_sections:
                for key, value in paper_sections.items():
                    salvaged_sections[key] = value
            
            latex_file = generate_latex_from_text(salvaged_sections)
            if latex_file:
                zip_path = create_zip(latex_file)
                if zip_path:
                    print(f"\n📦 Salvaged paper package created at: {zip_path}")
                
                return salvaged_sections
        
        return None

# =============================
# 🚀 Entry Point
# =============================

def main():
    print("📘 Welcome to the Enhanced IEEE Paper Generator")
    print("-----------------------------------------------------")
    
    # Install required packages if not already installed
    try:
        import importlib
        required_packages = ["langchain-google-genai", "langchain-core", "langchain"]
        for package in required_packages:
            if not importlib.util.find_spec(package.replace("-", "_")):
                print(f"📦 Installing {package}...")
                import subprocess
                subprocess.check_call(["pip", "install", package])
    except Exception as e:
        print(f"⚠️ Package installation error: {e}")
    
    try:
        topic = input("👉 Enter your research topic: ").strip()
        if not topic:
            topic = "Explainable AI in Medical Diagnosis"
            print(f"⚠️ No topic entered. Using default topic: {topic}")
        
        # Get additional details
        print("\n👉 Enter additional details (optional, press Enter to skip):")
        print("   Examples: specific techniques, datasets, focus areas, etc.")
        details = input("   Details: ").strip()
        
        # Get paper type preference
        print("\n👉 Select paper type:")
        print("   1. Research paper (empirical study with experiments)")
        print("   2. Survey/Review paper (comprehensive literature review)")
        print("   3. Methodology paper (novel method or algorithm)")
        print("   4. Case study (application in specific domain)")
        
        paper_type = input("   Enter choice (1-4, default: 1): ").strip() or "1"
        
        # Combine details based on paper type
        paper_details = details + "\n\n"
        if paper_type == "1":
            paper_details += "Paper Type: This should be a research paper with empirical experiments, results, and analysis."
        elif paper_type == "2":
            paper_details += "Paper Type: This should be a comprehensive survey/review paper that analyzes and synthesizes existing literature."
        elif paper_type == "3":
            paper_details += "Paper Type: This should be a methodology paper focusing on a novel method or algorithm with theoretical foundations."
        elif paper_type == "4":
            paper_details += "Paper Type: This should be a case study paper demonstrating application in a specific domain with practical insights."
        
        result = generate_paper_in_sections(topic, paper_details)
        if result:
            print("\n✅ Paper generation completed successfully!")
    except KeyboardInterrupt:
        print("\n\n⚠️ Process interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()