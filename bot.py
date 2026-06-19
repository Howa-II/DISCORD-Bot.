import discord
from discord.ext import commands
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

LANG_EMOJIS = {
    "🇬🇧": "English",
    "🇫🇷": "French",
    "🇸🇦": "Arabic",
    "🇯🇵": "Japanese",
    "🇮🇹": "Italian",
    "🇩🇪": "German",
    "🇪🇸": "Spanish",
    "🇷🇺": "Russian",
    "🇲🇦": "Maghrebi dialect",
    "🇵🇹": "Portuguese",
    "🇳🇱": "Dutch",
    "🇰🇷": "Korean",
    "🇨🇳": "Chinese",
    "🇷🇴": "Romanian",
    "🇵🇱": "Polish",
    "🇨🇿": "Czech",
    "🇧🇬": "Bulgarian",
    "🇭🇺": "Hungarian",
    "🇭🇷": "Croatian",
    "🇻🇳": "Vietnamese",
    "🇹🇭": "Thai",
}

LANG_TO_EMOJI = {v: k for k, v in LANG_EMOJIS.items()}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def process_translation(text: str, target_lang: str | None, mode: str) -> tuple[str, str]:
    supported = ", ".join(LANG_EMOJIS.values())

    if mode == "translate" and target_lang:
        prompt = (
            f"Do two things at once:\n"
            f"1. Detect the language of this text from this list ONLY: {supported}. If not in list, write UNKNOWN.\n"
            f"2. Translate the text to {target_lang}.\n\n"
            f"Reply in this exact format (2 lines only):\n"
            f"LANG: <detected language>\n"
            f"RESULT: <translation>\n\n"
            f"Text: {text}"
        )
    else:
        lang_instruction = f"in {target_lang}" if target_lang else "in the same language as the original text"
        prompt = (
            f"Do two things at once:\n"
            f"1. Detect the language of this text from this list ONLY: {supported}. If not in list, write UNKNOWN.\n"
            f"2. As a humorous Discord bot, reveal the hidden true meaning of this message based on Discord/gaming clichés. Reply {lang_instruction}, short and funny.\n\n"
            f"Reply in this exact format (2 lines only):\n"
            f"LANG: <detected language>\n"
            f"RESULT: <hidden truth>\n\n"
            f"Text: {text}"
        )

    response = model.generate_content(prompt)
    lines = response.text.strip().split("\n")
    source_lang = None
    result = ""

    for line in lines:
        if line.startswith("LANG:"):
            raw = line.replace("LANG:", "").strip()
            for lang in LANG_EMOJIS.values():
                if lang.lower() == raw.lower():
                    source_lang = lang
                    break
        elif line.startswith("RESULT:"):
            result = line.replace("RESULT:", "").strip()

    return source_lang, result


class TranslateView(discord.ui.View):
    def __init__(self, original_text: str, message_ref: discord.Message, invoker_id: int):
        super().__init__(timeout=120)
        self.original_text = original_text
        self.message_ref = message_ref
        self.invoker_id = invoker_id
        self.selected_values = []

        options = [discord.SelectOption(label="🔎 Back Thought", value="TRUTH", description="Reveals the hidden truth")]
        for emoji, lang in LANG_EMOJIS.items():
            options.append(discord.SelectOption(label=f"{emoji} {lang}", value=emoji))

        select = discord.ui.Select(
            placeholder="Choose a language or Back Thought...",
            min_values=1,
            max_values=2,
            options=options[:25],
            row=0
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel is not yours.", ephemeral=True)
            return

        values = interaction.data["values"]
        lang_values = [v for v in values if v != "TRUTH"]

        if len(lang_values) > 1:
            await interaction.response.send_message("❌ Choose only one language at a time.", ephemeral=True)
            return

        self.selected_values = values

        display = []
        if "TRUTH" in values:
            display.append("🔎 Back Thought")
        for v in lang_values:
            display.append(f"{v} {LANG_EMOJIS[v]}")

        await interaction.response.edit_message(
            content=f"## Translater\n**Message:** *{self.original_text[:80]}*\n\n**Selection:** {' + '.join(display)}\n\nConfirm with ✅",
            view=self
        )

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel is not yours.", ephemeral=True)
            return

        if not self.selected_values:
            await interaction.response.send_message("⚠️ Please select a language or Back Thought first!", ephemeral=True)
            return

        await interaction.response.edit_message(content="⏳ Processing...", view=None)
        self.stop()

        values = self.selected_values
        has_truth = "TRUTH" in values
        lang_values = [v for v in values if v != "TRUTH"]
        translator = interaction.user.mention
        supported_list = ", ".join(LANG_EMOJIS.values())

        try:
            if not has_truth and len(lang_values) == 1:
                # Translation only
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, result_text = process_translation(self.original_text, target_lang, "translate")

                if source_lang is None:
                    await interaction.edit_original_response(content=f"❌ **Language not registered.**\n**Supported:** {supported_list}")
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")
                if source_lang == target_lang:
                    # Same language — one line only
                    reply = f"{source_emoji} *(Already in {source_lang}.)* {translator}"
                else:
                    # Translation — two lines
                    reply = f"{source_emoji} {result_text}\nTranslated by {translator}"

            elif has_truth and len(lang_values) == 0:
                # Truth only — two lines
                source_lang, result_text = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await interaction.edit_original_response(content=f"❌ **Language not registered.**\n**Supported:** {supported_list}")
                    return

                reply = f"{result_text}\nRevealed by {translator}"

            elif has_truth and len(lang_values) == 1:
                # Truth + translation
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, truth_text = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await interaction.edit_original_response(content=f"❌ **Language not registered.**\n**Supported:** {supported_list}")
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")

                if source_lang == target_lang:
                    # Same language — three lines
                    reply = f"{source_emoji} *(Already in {target_lang}.)* {translator}\n{truth_text}\nRevealed by {translator}"
                else:
                    # Translate the truth — two lines
                    _, translated_truth = process_translation(truth_text, target_lang, "translate")
                    reply = f"{source_emoji} {translated_truth}\nRevealed and Translated by {translator}"

            else:
                await interaction.edit_original_response(content="❌ Invalid combination.")
                return

            await self.message_ref.reply(reply)
            await interaction.edit_original_response(content="✅ Done!")

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Error: {str(e)}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel is not yours.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)
        self.stop()


@bot.tree.context_menu(name="Translater")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content.strip():
        await interaction.response.send_message("❌ This message contains no text.", ephemeral=True)
        return

    view = TranslateView(
        original_text=message.content,
        message_ref=message,
        invoker_id=interaction.user.id
    )

    await interaction.response.send_message(
        f"## Translater\n**Message:** *{message.content[:80]}{'...' if len(message.content) > 80 else ''}*\n\nChoose a language or Back Thought, then confirm with ✅",
        view=view,
        ephemeral=True
    )


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} command(s) synced")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    print(f"✅ Bot connected: {bot.user} (ID: {bot.user.id})")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
    
