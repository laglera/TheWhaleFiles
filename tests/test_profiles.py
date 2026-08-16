import unittest

from app.names import clean_person_name, short_name
from app.profiles import score_entity


def entity(instance_of=("Q5",), occupations=(), positions=(), citizenship=()):
    """Entidad de Wikidata mínima, con la forma que devuelve wbgetentities."""

    def claim(qid):
        return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}

    return {
        "claims": {
            "P31": [claim(q) for q in instance_of],
            "P106": [claim(q) for q in occupations],
            "P39": [claim(q) for q in positions],
            "P27": [claim(q) for q in citizenship],
        }
    }


class NameCleaningTests(unittest.TestCase):
    def test_removes_titles_initials_and_suffixes(self):
        cases = {
            "John J Mr McGuire": "John McGuire",
            "Marjorie Taylor Mrs Greene": "Marjorie Taylor Greene",
            "Hon. Nancy Pelosi": "Nancy Pelosi",
            "Christian D. Menefee": "Christian Menefee",
            "Mark Dr Green": "Mark Green",
            "Elon Musk": "Elon Musk",
        }
        for raw, expected in cases.items():
            self.assertEqual(clean_person_name(raw), expected, raw)

    def test_variants_of_the_same_person_collapse(self):
        variants = ["C. Scott Franklin", "Scott Mr Franklin", "Scott Franklin", "Scott Scott Franklin"]
        self.assertEqual({clean_person_name(name) for name in variants}, {"Scott Franklin"})

    def test_professional_suffixes_are_dropped(self):
        variants = ["Neal Patrick Dunn FACS", "Neal Patrick Facs Dunn", "Neal Patrick FACS Dunn"]
        self.assertEqual({clean_person_name(name) for name in variants}, {"Neal Patrick Dunn"})

    def test_quoted_nickname_becomes_the_first_name(self):
        # Se le conoce como Bobby Scott, que es además el título del artículo.
        self.assertEqual(clean_person_name('Robert "Bobby" Scott'), "Bobby Scott")

    def test_short_name_drops_middle_names(self):
        self.assertEqual(short_name("Donald Sternoff Beyer"), "Donald Beyer")
        self.assertEqual(short_name("Elon Musk"), "Elon Musk")

    def test_never_returns_empty(self):
        self.assertEqual(clean_person_name("Mr"), "Mr")
        self.assertEqual(clean_person_name(""), "")


class EntityScoringTests(unittest.TestCase):
    def test_congressman_scores_above_threshold(self):
        person = entity(occupations=["Q82955"], positions=["Q13218630"], citizenship=["Q30"])
        self.assertGreaterEqual(score_entity(person, "congress"), 4)

    def test_executive_scores_above_threshold(self):
        person = entity(occupations=["Q131524", "Q81096"], positions=["Q484876"], citizenship=["Q30"])
        self.assertGreaterEqual(score_entity(person, "business"), 4)

    def test_a_book_about_a_person_is_rejected(self):
        # El caso real: buscar "Elon Musk" devuelve antes la biografía escrita
        # sobre él que la persona.
        book = entity(instance_of=["Q571"])
        self.assertEqual(score_entity(book, "business"), 0)

    def test_unrelated_homonym_stays_below_threshold(self):
        # "John McGuire" también es un actor: es humano, pero sin cargo ni
        # ocupación política no debe ganar la ficha del congresista.
        actor = entity(occupations=["Q33999"], citizenship=["Q30"])
        self.assertLess(score_entity(actor, "congress"), 4)


if __name__ == "__main__":
    unittest.main()
