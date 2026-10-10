# GitHub upload steps

From your Mac Terminal, after unzipping this folder:

```bash
cd ~/Downloads/CS30401_Lab1_GitHub_Ready
git init
git add .
git commit -m "Add CS30401 Lab 1 reproducibility package"
git branch -M main
```

Create an empty GitHub repository in the browser, then copy its HTTPS URL and run:

```bash
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Before submission, add the final `report.pdf` at the repository root if your team wants the GitHub repository to mirror the submission package. The course submission ZIP itself should still follow the handout-required structure (`report.pdf`, `README.md`, `code/`).
