import unittest

from native_chrome import verification_checkbox


class VerificationCheckboxTests(unittest.TestCase):
    def node(self, **changes):
        node = {"role": {"value": "checkbox"},
                "name": {"value": "Verify you are human"},
                "backendDOMNodeId": 42, "properties": []}
        node.update(changes)
        return node

    def test_only_named_unchecked_verification_checkbox(self):
        self.assertTrue(verification_checkbox(self.node()))
        self.assertFalse(verification_checkbox(self.node(role={"value": "button"})))
        self.assertFalse(verification_checkbox(self.node(name={"value": "Buy now"})))
        self.assertFalse(verification_checkbox(self.node(backendDOMNodeId=None)))
        self.assertFalse(verification_checkbox(self.node(properties=[
            {"name": "disabled", "value": {"value": True}}])))
        for value in (True, "true"):
            self.assertFalse(verification_checkbox(self.node(properties=[
                {"name": "checked", "value": {"value": value}}])))


if __name__ == "__main__":
    unittest.main()
