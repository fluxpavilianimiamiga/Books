# Books

A phone reader that narrates EPUBs. `index.html` is the whole app. On every push, GitHub Actions
publishes the app to GitHub Pages immediately, then narrates each book in `books.txt` with Kokoro
(five voices, sentence timings) and republishes with the audio alongside.

Setup once: Settings → Pages → Source: **GitHub Actions**.
