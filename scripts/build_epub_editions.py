#!/usr/bin/env python3
"""
scripts/build_epub_editions.py
Builds reflowable, standard-compliant EPUB3 editions for all three volumes of
'THE SACRED SANCTUM: FOUNDATIONS OF SOVEREIGN INTELLIGENCE'.
"""

import os
import markdown
from ebooklib import epub

def create_volume_epub(vol_id, title, author, md_path, out_epub):
    book = epub.EpubBook()
    book.set_identifier(f"imf-sacred-sanctum-v0{vol_id}")
    book.set_title(title)
    book.set_language('en')
    book.add_author(author)

    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Convert markdown to HTML
    html_content = markdown.markdown(md_text, extensions=['extra', 'tables'])

    c1 = epub.EpubHtml(title=title, file_name='text.xhtml', lang='en')
    c1.content = f"""
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
      <title>{title}</title>
      <style>
        body {{ font-family: serif; line-height: 1.6; margin: 5%; }}
        h1, h2, h3 {{ font-family: sans-serif; color: #1e3a8a; }}
        pre, code {{ font-family: monospace; background: #f3f4f6; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; }}
      </style>
    </head>
    <body>
      {html_content}
    </body>
    </html>
    """
    book.add_item(c1)

    # Table of contents
    book.toc = (epub.Link('text.xhtml', title, 'intro'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine
    book.spine = ['nav', c1]

    os.makedirs(os.path.dirname(out_epub), exist_ok=True)
    epub.write_epub(out_epub, book)
    print(f"[+] Successfully built EPUB: {out_epub} ({os.path.getsize(out_epub) / 1024:.1f} KB)")

def main():
    vols = [
        (1, "The Sacred Sanctum: Foundations of Sovereign Intelligence - Vol I", "Stratum Research Group",
         "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md",
         "docs/thesis/compiled/The_Sacred_Sanctum_v01.epub"),
        (2, "The Sacred Sanctum: Foundations of Sovereign Intelligence - Vol II", "Stratum Research Group",
         "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md",
         "docs/thesis/compiled/The_Sacred_Sanctum_v02.epub"),
        (3, "The Sacred Sanctum: Foundations of Sovereign Intelligence - Vol III", "Stratum Research Group",
         "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md",
         "docs/thesis/compiled/The_Sacred_Sanctum_v03.epub")
    ]

    for v in vols:
        create_volume_epub(*v)

if __name__ == '__main__':
    main()
