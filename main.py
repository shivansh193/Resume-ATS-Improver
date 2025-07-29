import os
import sys
import subprocess
import shutil
import tempfile
import google.generativeai as genai

# --- Configuration ---
# Configure the Gemini API key from environment variables for security
try:
    genai.configure(api_key="Put API Key here")
except KeyError:
    print("FATAL ERROR: The GOOGLE_API_KEY environment variable is not set.")
    print("Please get an API key from Google AI Studio and set the environment variable.")
    sys.exit(1)

# --- The AI Prompt ---
# This is the most important part. It tells the AI exactly what to do and what NOT to do.
SYSTEM_PROMPT = """
You are an expert career coach and professional resume editor who specializes in tailoring LaTeX resumes for specific job descriptions.

Your task is to subtly modify the provided LaTeX resume to better align with the requirements and keywords found in the provided job description.

**CRITICAL RULES:**
1.  **DO NOT CHANGE CORE FACTS:** You must not change the candidate's name, contact information, university, degree, previous employers, job titles, or dates of employment. The core factual history is sacred and must be preserved.
2.  **DO NOT INVENT:** Do not invent new skills, projects, or experiences. You can only work with the information already present in the resume.
3.  **FOCUS ON REPHRASING AND HIGHLIGHTING:** Your main job is to:
    - Rephrase bullet points under the 'Experience' and 'Projects' sections to use language and keywords from the job description.
    - Reorder bullet points within a single job experience to highlight the most relevant achievements first.
    - Slightly tweak the 'Summary' or 'Objective' section to better match the target role.
4.  **MAINTAIN VALID LATEX:** The output MUST be a complete, valid, and compilable LaTeX document. Do not break the LaTeX syntax.
5.  **RAW OUTPUT ONLY:** Your entire output must be ONLY the raw LaTeX source code. Do not include any commentary, explanations, or markdown like ```latex ... ```.
6.  **DO NOT USE ANY SPECIFC STAT FROM THE JOB DESCRIPTION, JUST EDIT THE ORIGINAL RESUME TO BE ATS FREINDLY WITH THE JD**
7. **NOFLUFF ONLY LATEX CODE IN YOUR OUTPUT**
Here is the job description and the resume. Modify the resume according to these rules.
"""

def get_customized_latex(jd_text, resume_latex):
    """
    Sends the job description and resume to Gemini and returns the modified LaTeX code.
    """
    print("🤖 Sending resume and job description to Gemini for tailoring...")
    
    # Set up the model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    full_prompt = f"{SYSTEM_PROMPT}\n\n--- JOB DESCRIPTION ---\n{jd_text}\n\n--- LATEX RESUME ---\n{resume_latex}"
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"❌ An error occurred with the Gemini API: {e}")
        return None

def compile_latex_to_pdf(latex_code, output_filename):
    """
    Compiles a string of LaTeX code into a PDF file.
    Returns True on success, False on failure.
    """
    # Create a temporary directory to keep things clean
    with tempfile.TemporaryDirectory() as temp_dir:
        tex_filepath = os.path.join(temp_dir, 'source.tex')
        pdf_filepath = os.path.join(temp_dir, 'source.pdf')
        log_filepath = os.path.join(temp_dir, 'source.log')

        with open(tex_filepath, 'w', encoding='utf-8') as f:
            f.write(latex_code)

        command = [
            'pdflatex',
            '-interaction=nonstopmode',
            f'-output-directory={temp_dir}',
            tex_filepath
        ]

        print(f"⏳ Compiling LaTeX... (This may take a moment)")
        try:
            # Run twice to resolve references (e.g., table of contents)
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("❌ LaTeX compilation failed!")
            if isinstance(e, FileNotFoundError):
                 print("ERROR: 'pdflatex' command not found.")
                 print("Please ensure you have a TeX distribution (like TeX Live, MiKTeX) installed and in your system's PATH.")
                 return False

            if os.path.exists(log_filepath):
                with open(log_filepath, 'r') as log_file:
                    print("\n--- COMPILATION LOG ---\n")
                    print(log_file.read())
            return False

        # If compilation succeeded, copy the PDF to the final destination
        if os.path.exists(pdf_filepath):
            shutil.copy(pdf_filepath, output_filename)
            return True
        else:
            print("❌ Compilation seemed to succeed, but no PDF was found.")
            return False

def main():
    """Main function to run the resume tailoring process."""
    if len(sys.argv) != 3:
        print("Usage: python resume_tailor.py <path/to/resume.tex> <path/to/job_description.txt>")
        sys.exit(1)

    resume_file_path = sys.argv[1]
    jd_file_path = sys.argv[2]

    # Read input files
    try:
        with open(resume_file_path, 'r', encoding='utf-8') as f:
            original_resume_latex = f.read()
        with open(jd_file_path, 'r', encoding='utf-8') as f:
            jd_text = f.read()
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e.filename}")
        sys.exit(1)

    # Get tailored LaTeX from Gemini
    customized_latex = get_customized_latex(jd_text, original_resume_latex)

    if not customized_latex:
        print("Could not get a response from the AI. Aborting.")
        sys.exit(1)

    # --- User Confirmation Step ---
    print("\n" + "="*80)
    print("✅ AI has returned the tailored resume code. Please review the changes:")
    print("="*80 + "\n")
    print(customized_latex)
    print("\n" + "="*80)

    while True:
        confirm = input("Do you want to save this version as a PDF? (y/n): ").lower().strip()
        if confirm in ['y', 'yes']:
            break
        elif confirm in ['n', 'no']:
            print("Aborted by user.")
            sys.exit(0)
        else:
            print("Invalid input. Please enter 'y' or 'n'.")

    # --- PDF Saving Step ---
    while True:
        company_name = os.path.basename(jd_file_path).split('.')[0].replace(' ', '_')
        default_name = f"Resume_JohnDoe_for_{company_name}.pdf"
        pdf_filename = input(f"Enter the desired PDF filename (default: {default_name}): ").strip()
        if not pdf_filename:
            pdf_filename = default_name
        
        # Basic security: prevent path traversal
        if os.path.dirname(pdf_filename):
            print("❌ Invalid filename. Please do not include directory paths.")
            continue

        if not pdf_filename.lower().endswith('.pdf'):
            pdf_filename += '.pdf'
        
        break

    # Compile the final PDF
    if compile_latex_to_pdf(customized_latex, pdf_filename):
        print(f"\n✨ Success! Your tailored resume has been saved as '{pdf_filename}'")
    else:
        print("\n❌ Failed to create the PDF. Please check the compilation log above.")

if __name__ == "__main__":
    main()
