# Fonctionalities

## Use cases
- I use the Extra field as a hint, showing a list of similar answers to other cards. But it's a hint only for some fields, it contains the answer for other fields. But in a cloze note, we can't chose if we want to show the Extra field for specific cloze fields, not all of them. Furthermore, I have sevaral cloze notes who follow the same patterns. So I transform the Cloze cards into basic cards where I can adapt the card templates : for some cards, I show the Extra field in the question, for others, in the Answer.

# Installation

- Careful: if in WSL, must copy the collection to WSL file system. Refering to the collection in Windows filesystem (`/mnt/c` etc) seems to create an empty collection. TODO: check why. anki library in linux is different?

# TODOs
- Handle the repetition of cloze field number (several {{c1:...}})
- Allow for mistakes => undo or else ?

`cp "/mnt/c/Users/User/AppData/Roaming/Anki2/User 1/collection.anki2" ~/anki-editing/anki-collection-editing/data/collection.anki2`