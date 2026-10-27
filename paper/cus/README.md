# Computational Urban Science submission (version 1.2)

Built by `python -I -m planarena.paper` from `results/` and the `.tex.in` templates here. Do not edit the `.tex` files; edit the templates. The original paper (`paper/paper.tex.in`, v1.1) is unchanged.

| Upload as | File |
|---|---|
| Title page (not shown to reviewers) | `title_page.pdf` and `title_page.tex` |
| Anonymised manuscript | `manuscript.pdf` and its source: `manuscript.tex`, `figures/` |
| Online Resource 1 (ESM_1.pdf) | `online_resource_1.pdf` (source `online_resource_1.tex`) |
| Figures | `figures/Fig1.pdf` (architecture), `Fig2–4.png` (Studio), `Fig5–6.eps`/`.pdf` (charts); `ESM_Fig1–2` belong to Online Resource 1 |
| Cover letter | `cover_letter.md` (draft) |

What this version changes for the journal:
- **Double-blind:** no author in the manuscript or Online Resource 1, and the code linked through an anonymised mirror.
- **Citations:** author–year in the text, with an alphabetical APA 7 reference list and DOI links (`planarena/apa.py`).
- **Datasets:** cited in the references (`data_refs.yaml`).
- **Statements and Declarations:** included, with the use of AI tools stated in the Methods section.
- **Abstract:** AUC is defined there.
- **Units:** SI, with US units in parentheses where they are a source's threshold.
- **Tables:** cited in order; the former appendix tables moved to Online Resource 1.
- **Figure captions:** "Fig." style with no final period.
- **Charts:** at least 8 pt Arial, markers and hatching besides colour, no titles inside figures, and separate figure files.
- **Links:** the online Studio and game.

**Before submitting (author):**
1. **Anonymised mirror.** The branch `cus-review` is the anonymised copy for reviewers. It has no PDFs, no title page or cover letter, and no name, affiliation or user name. It is built by `python -I -m planarena.tools.review_copy`; after any change on main, rerun it and push with `git push origin cus-review`. At https://anonymous.4open.science, sign in with GitHub and choose:
   - repository `ParyaPayami/PlanArena`, branch `cus-review`;
   - repository ID `planarena-cus` (the manuscript links `https://anonymous.4open.science/r/planarena-cus`);
   - automatic updates on.

   Also add "Payami", "ParyaPayami", "ppayami" and "University of Wisconsin" as terms to anonymise, as a second safeguard.
2. **Title page.** Fill in the ORCID, the acknowledgements and the funding statement.
3. **Archive.** Archive the release on Zenodo and add its DOI to the title page.
4. **Submission system.** Choose "Original Paper", and the collection "Human-Centered Urban Digital Twins and Policy Insights" if you want it (deadline November 20, 2026). Enter the competing-interest and author-contribution statements in the interface as well.
5. **Fee.** Ask the UWM Libraries about the article processing charge, and request any waiver at submission.
