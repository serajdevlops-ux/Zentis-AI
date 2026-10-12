import json
import os
import re
import random
import threading

from pathlib import Path
from datetime import datetime, timezone


class ZentraAI:
    VERSION = "0.1.0"

    def __init__(self, memory_path=None):
        self.lock = threading.RLock()

        if memory_path is None:
            # Android: use the application's private files directory.
            # Desktop: use ~/.zentra/memory.json.
            app_data = os.environ.get("ZENTRA_DATA_DIR")

            if app_data:
                data_dir = Path(app_data)
            else:
                data_dir = Path.home() / ".zentra"

            memory_path = data_dir / "memory.json"

        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        self.memory = {
            "version": 1,
            "facts": {},
            "conversations": []
        }

        self._load_memory()

    def _load_memory(self):
        with self.lock:
            if not self.memory_path.exists():
                self._save_memory()
                return

            try:
                with self.memory_path.open(
                    "r",
                    encoding="utf-8"
                ) as file:
                    loaded = json.load(file)

                if isinstance(loaded, dict):
                    self.memory.update(loaded)

                if not isinstance(self.memory.get("facts"), dict):
                    self.memory["facts"] = {}

                if not isinstance(
                    self.memory.get("conversations"), list
                ):
                    self.memory["conversations"] = []

            except (OSError, json.JSONDecodeError):
                # Preserve the existing file rather than overwriting
                # potentially recoverable data.
                self.memory = {
                    "version": 1,
                    "facts": {},
                    "conversations": []
                }

    def _save_memory(self):
        with self.lock:
            self.memory_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            temporary = self.memory_path.with_suffix(".tmp")

            with temporary.open("w", encoding="utf-8") as file:
                json.dump(
                    self.memory,
                    file,
                    ensure_ascii=False,
                    indent=2
                )

            temporary.replace(self.memory_path)

    @staticmethod
    def normalize(text):
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s']", "", text)
        return text

    def teach(self, key, value):
        key = str(key).strip()
        value = str(value).strip()

        if not key or not value:
            return "Please provide both a fact and its value."

        if len(key) > 200 or len(value) > 2000:
            return "That memory is too long."

        with self.lock:
            self.memory["facts"][self.normalize(key)] = {
                "key": key,
                "value": value,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }

            self._save_memory()

        return f"I've saved that: {key} = {value}"

    def recall(self, query):
        normalized = self.normalize(query)

        with self.lock:
            facts = self.memory.get("facts", {})

            # Exact key lookup.
            if normalized in facts:
                return facts[normalized]["value"]

            # Simple natural-language lookup.
            for key, fact in facts.items():
                if key and (
                    key in normalized or normalized in key
                ):
                    return fact["value"]

        return None

    def _remember_conversation(self, role, text):
        with self.lock:
            self.memory["conversations"].append({
                "role": role,
                "text": text[:5000],
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat()
            })

            # Keep the most recent 200 entries.
            self.memory["conversations"] = (
                self.memory["conversations"][-200:]
            )

            self._save_memory()

    def generate(self, prompt):
        prompt = str(prompt).strip()

        if not prompt:
            return "Please enter a message."

        if len(prompt) > 5000:
            return "That message is too long. Please shorten it."

        normalized = self.normalize(prompt)

        self._remember_conversation("user", prompt)

        answer = self._respond(normalized, prompt)

        self._remember_conversation("assistant", answer)

        return answer

    def _respond(self, normalized, original):
        # Teaching syntax:
        # teach: favorite color = blue
        if normalized.startswith("teach "):
            content = original[6:].strip()

            if "=" not in content:
                return (
                    "Use this format:\n"
                    "teach: favorite color = blue"
                )

            key, value = content.split("=", 1)

            key = re.sub(
                r"^\s*[:\-]\s*",
                "",
                key
            ).strip()

            return self.teach(key, value)

        if normalized.startswith("teach:"):
            content = original.split(":", 1)[1].strip()

            if "=" not in content:
                return (
                    "Use this format:\n"
                    "teach: favorite color = blue"
                )

            key, value = content.split("=", 1)
            return self.teach(key, value)

        if normalized in {"help", "commands"}:
            return (
                "I'm Zentra, a local Python-based assistant.\n\n"
                "Available commands:\n"
                "• teach: favorite color = blue\n"
                "• What is my favorite color?\n"
                "• What time is it?\n"
                "• hello\n\n"
                "My current reasoning and language abilities "
                "are limited. This starter engine uses rules "
                "and stored facts rather than a trained model."
            )

        # Recall facts the user has taught Zentra.
        if normalized.startswith("what is my "):
            key = normalized[len("what is my "):].rstrip("? ")
            answer = self.recall(key)

            if answer is not None:
                return answer

        if normalized.startswith("remembered "):
            key = normalized[len("remembered "):].strip()
            answer = self.recall(key)

            if answer is not None:
                return answer

        if normalized.startswith("what do you know about "):
            key = normalized[len("what do you know about "):]
            answer = self.recall(key)

            if answer is not None:
                return answer

        # Greetings.
        greetings = {
            "hi",
            "hello",
            "hey",
            "hello zentra",
            "hi zentra",
            "hey zentra"
        }

        if normalized in greetings:
            return random.choice([
                "Hello! I'm Zentra. How can I help?",
                "Hi! What would you like to work on?",
                "Hello. What would you like to discuss?"
            ])

        if "your name" in normalized:
            return "My name is Zentra AI."

        if normalized in {
            "who are you",
            "what are you",
            "what is zentra"
        }:
            return (
                "I'm Zentra AI, a Python-based assistant. "
                "This version uses rules and persistent memory. "
                "A language model can be integrated later "
                "to provide more advanced conversation."
            )

        if "what time is it" in normalized:
            return datetime.now().astimezone().strftime(
                "The current time is %H:%M."
            )

        if normalized in {
            "thank you",
            "thanks",
            "thank you zentra"
        }:
            return "You're welcome."

        # Try to find a matching learned fact.
        answer = self.recall(normalized)

        if answer is not None:
            return answer

        # A basic fallback.
        return (
            "I don't know how to answer that yet. "
            "You can teach me a fact using:\n"
            "teach: topic = information"
        )

    def clear_conversations(self):
        with self.lock:
            self.memory["conversations"] = []
            self._save_memory()

        return "Conversation records cleared. Saved facts remain."

    def forget(self, key):
        normalized = self.normalize(key)

        with self.lock:
            if normalized not in self.memory["facts"]:
                return "I couldn't find that saved fact."

            del self.memory["facts"][normalized]
            self._save_memory()

        return f"I forgot the saved fact: {key}"


# Command-line mode for testing Zentra on a computer.
if __name__ == "__main__":
    ai = ZentraAI()

    print(f"Zentra AI {ai.VERSION}")
    print("Type 'exit' to quit.")
    print("Type 'help' to see available commands.\n")

    while True:
        try:
            message = input("You: ").strip()

            if message.lower() in {"exit", "quit"}:
                print("Zentra: Goodbye.")
                break

            print("Zentra:", ai.generate(message))

        except (KeyboardInterrupt, EOFError):
            print("\nZentra: Goodbye.")
            break
