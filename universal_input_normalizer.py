import os
import mimetypes
from pathlib import Path

from langdetect import detect
from deep_translator import GoogleTranslator

# ---------- OPTIONAL IMPORTS ----------
# Install only what you need from requirements.txt

try:
    import whisper
except:
    whisper = None

try:
    import fitz  # PyMuPDF
except:
    fitz = None

try:
    import pandas as pd
except:
    pd = None

try:
    import docx
except:
    docx = None

try:
    from PIL import Image
    import pytesseract
except:
    Image = None
    pytesseract = None

try:
    from Bio import SeqIO
except:
    SeqIO = None

try:
    from rdkit import Chem
except:
    Chem = None


# ---------- TRANSLATION ----------

def to_english(text):
    if not text.strip():
        return ""

    try:
        lang = detect(text)

        if lang == "en":
            return text

        return GoogleTranslator(source='auto', target='en').translate(text)

    except:
        return text


# ---------- TEXT ----------

def process_text(text):
    english = to_english(text)

    return f"English Prompt:\\n{english}"


# ---------- AUDIO ----------

def process_audio(file_path):
    if whisper is None:
        return "Whisper not installed."

    model = whisper.load_model("base")

    result = model.transcribe(file_path)

    text = result["text"]

    english = to_english(text)

    return f"English Prompt:\\n{english}"


# ---------- PDF ----------

def process_pdf(file_path):
    if fitz is None:
        return "PyMuPDF not installed."

    doc = fitz.open(file_path)

    text = ""

    for page in doc:
        text += page.get_text()

    english = to_english(text[:10000])

    return f"English Prompt:\\nSummarize and analyze the following document:\\n\\n{english}"


# ---------- DOCX ----------

def process_docx(file_path):
    if docx is None:
        return "python-docx not installed."

    doc = docx.Document(file_path)

    text = "\\n".join([p.text for p in doc.paragraphs])

    english = to_english(text[:10000])

    return f"English Prompt:\\nExtract insights from this document:\\n\\n{english}"


# ---------- IMAGE ----------

def process_image(file_path):
    if Image is None or pytesseract is None:
        return "Pillow or pytesseract not installed."

    image = Image.open(file_path)

    text = pytesseract.image_to_string(image)

    english = to_english(text)

    return f"English Prompt:\\nAnalyze this image content:\\n\\n{english}"


# ---------- CSV/XLSX ----------

def process_spreadsheet(file_path):
    if pd is None:
        return "pandas not installed."

    ext = Path(file_path).suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    preview = df.head(10).to_string()

    return f"English Prompt:\\nAnalyze this dataset:\\n\\n{preview}"


# ---------- FASTA ----------

def process_fasta(file_path):
    if SeqIO is None:
        return "Biopython not installed."

    sequences = []

    for record in SeqIO.parse(file_path, "fasta"):
        sequences.append(
            f"Sequence ID: {record.id}, Length: {len(record.seq)}"
        )

    joined = "\\n".join(sequences)

    return f"English Prompt:\\nAnalyze these biological sequences:\\n\\n{joined}"


# ---------- SMILES / SDF / MOL ----------

def process_chem(file_path):
    if Chem is None:
        return "RDKit not installed."

    ext = Path(file_path).suffix.lower()

    mol = None

    if ext == ".smi":
        with open(file_path) as f:
            smiles = f.read().strip()

        mol = Chem.MolFromSmiles(smiles)

    elif ext == ".mol":
        mol = Chem.MolFromMolFile(file_path)

    elif ext == ".sdf":
        supplier = Chem.SDMolSupplier(file_path)
        mol = supplier[0]

    if mol is None:
        return "Could not parse chemical structure."

    formula = Chem.rdMolDescriptors.CalcMolFormula(mol)

    return f"English Prompt:\\nAnalyze this chemical compound with molecular formula {formula}."


# ---------- ROUTER ----------

def process_input(user_input):

    if not os.path.isfile(user_input):
        return "File Format Error"
    
    else:
        ext = Path(user_input).suffix.lower()

        if ext == ".txt":
            with open(user_input, "r", encoding="utf-8") as f:
                text = f.read()
            return process_text(text)

        if ext in [".mp3", ".wav", ".m4a"]:
            return process_audio(user_input)

        elif ext == ".pdf":
            return process_pdf(user_input)

        elif ext in [".docx"]:
            return process_docx(user_input)

        elif ext in [".png", ".jpg", ".jpeg"]:
            return process_image(user_input)

        elif ext in [".csv", ".xlsx"]:
            return process_spreadsheet(user_input)

        elif ext in [".fasta", ".fa"]:
            return process_fasta(user_input)

        elif ext in [".smi", ".mol", ".sdf"]:
            return process_chem(user_input)

        else:
            return f"Unsupported file type: {ext}"

def process_folder(folder_path):

    if not os.path.isdir(folder_path):

        return "Invalid folder path."

    results = {}

    for filename in os.listdir(folder_path):

        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path):

            print(f"Processing: {filename}")

            try:

                result = process_input(file_path)

                results[filename] = result

                # Delete file after successful processing

                os.remove(file_path)

                print(f"Deleted: {filename}")

            except Exception as e:

                results[filename] = f"Error: {str(e)}"

    return results


# ---------- MAIN ----------

if __name__ == "__main__":
    prompt=""
    result = process_folder("input_folder_main")
    for filename,output in result.items():
        prompt += output + "\n"
    with open("input_folder/input.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
