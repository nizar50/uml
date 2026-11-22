"""Extraction du texte d'un fichier PDF ou Word (.docx) importé par l'enseignant."""


def extraire_texte(fichier):
    nom = fichier.name.lower()
    fichier.seek(0)
    try:
        if nom.endswith(".docx"):
            from docx import Document

            doc = Document(fichier)
            blocs = [p.text for p in doc.paragraphs if p.text.strip()]
            for tableau in doc.tables:
                for ligne in tableau.rows:
                    cellules = [c.text.strip() for c in ligne.cells if c.text.strip()]
                    if cellules:
                        blocs.append(" | ".join(cellules))
            texte = "\n\n".join(blocs)
        elif nom.endswith(".pdf"):
            from pypdf import PdfReader

            lecteur = PdfReader(fichier)
            pages = [(page.extract_text() or "").strip() for page in lecteur.pages]
            texte = "\n\n".join(p for p in pages if p)
        else:
            texte = ""
    finally:
        fichier.seek(0)
    return texte.strip()
