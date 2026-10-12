import json
import re
from pathlib import Path


class ZentraAI:
    def __init__(self, storage_path=None):
        self.storage_path = Path(
            storage_path or (
                Path.home() / ".zentra" / "memory.json"
            )
        )

        self.conversations = []
        self.knowledge = {}

        self.load_memory()

    def tokenize(self, text):
        """Convert text to normalized tokens."""
        return re.findall(r"\b\w+\b", text.lower())

    def load_memory(self):
        """Restore memory from persistent storage."""
        try:
            if not self.storage_path.exists():
                return

            data = json.loads(
                self.storage_path.read_text(encoding="utf-8")
            )

            self.conversations = data.get("conversations", [])
            self.knowledge = data.get("knowledge", {})

        except (OSError, ValueError, TypeError):
            self.conversations = []
            self.knowledge = {}

    def save_memory(self):
        """Persist memory between application launches."""
        try:
            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            data = {
                "conversations": self.conversations[-1000:],
                "knowledge": self.knowledge
            }

            temporary_path = self.storage_path.with_suffix(".tmp")

            temporary_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            temporary_path.replace(self.storage_path)

        except OSError:
            pass

    def remember(self, user_message, response):
        """Store a conversation."""
        self.conversations.append({
            "user": user_message,
            "assistant": response
        })

        self.conversations = self.conversations[-1000:]
        self.save_memory()

    def teach(self, prompt, response):
        """Teach the engine a direct response association."""
        prompt = prompt.strip().lower()
        response = response.strip()

        if not prompt or not response:
            return False

        self.knowledge[prompt] = response
        self.save_memory()

        return True

    def recall(self, message):
        """Find an exact match in previously stored conversations."""
        normalized = message.strip().lower()

        for item in reversed(self.conversations):
            if item.get("user", "").strip().lower() == normalized:
                return item.get("assistant")

        return None

    def generate(self, message):
        """Generate a response using the engine's current knowledge."""
        message = message.strip()

        if not message:
            return "Please enter a message."

        normalized = message.lower()
        tokens = self.tokenize(message)

        if normalized in self.knowledge:
            response = self.knowledge[normalized]

        elif normalized in {"hi", "hello", "hey", "hello zentra"}:
            response = "Hello! I'm Zentra, an AI we're building from scratch."

        elif "who are you" in normalized:
            response = (
                "I'm Zentra AI. My engine is being developed in Python, "
                "with the goal of eventually learning through a neural network."
            )

        elif "what can you do" in normalized:
            response = (
                "My current engine can store conversations, remember "
                "exact previous questions, and learn manually supplied "
                "question-and-answer pairs. A trained language model "
                "has not been implemented yet."
            )

        elif "your name" in normalized:
            response = "My name is Zentra."

        elif "how are you" in normalized:
            response = (
                "I'm operating normally. My current capabilities are "
                "limited by the engine implemented so far."
            )

        else:
            remembered = self.recall(message)

            if remembered:
                response = remembered
            else:
                response = (
                    "I don't know how to answer that yet. "
                    "You can teach me a response, and I'll save it "
                    "in my local knowledge store."
                )

        self.remember(message, response)
        return response

    def reset_memory(self):
        """Clear stored conversations and learned responses."""
        self.conversations.clear()
        self.knowledge.clear()
        self.save_memory()


if __name__ == "__main__":
    ai = ZentraAI()

    print("Zentra AI — Python engine")
    print("Commands: /teach question | answer, /reset, /exit")

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nZentra: Goodbye.")
            break

        if message.lower() == "/exit":
            break

        if message.lower() == "/reset":
            ai.reset_memory()
            print("Zentra: Memory cleared.")
            continue

        if message.startswith("/teach "):
            content = message[len("/teach "):]

            if "|" not in content:
                print(
                    "Zentra: Use /teach question | answer"
                )
                continue

            question, answer = content.split("|", 1)

            if ai.teach(question, answer):
                print("Zentra: I've saved that response.")
            else:
                print("Zentra: Both question and answer are required.")

            continue

        print("Zentra:", ai.generate(message))
