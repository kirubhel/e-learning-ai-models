import Levenshtein
t = "i love coding"
h = "i coding"
print(Levenshtein.editops(t, h))
print(Levenshtein.distance(t, h))
