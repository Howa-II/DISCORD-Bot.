import discord
from discord.ext import commands
from google import genai
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def generate(prompt):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

LANG_EMOJIS = {
    "🇺🇸": "American English",
    "🇲🇦": "Amazigh",
    "🇸🇦": "Arabic",
    "🇦🇺": "Australian English",
    "🇧🇷": "Brazilian Portuguese",
    "🇬🇧": "British English",
    "🇧🇬": "Bulgarian",
    "🇨🇳": "Chinese",
    "🇭🇷": "Croatian",
    "🇨🇿": "Czech",
    "🇩🇰": "Danish",
    "🇳🇱": "Dutch",
    "🇪🇬": "Egyptian Arabic",
    "🇫🇮": "Finnish",
    "🇫🇷": "French",
    "🇩🇪": "German",
    "🇬🇷": "Greek",
    "🇵🇸": "Hebrew",
    "🇮🇳": "Hindi",
    "🇭🇺": "Hungarian",
    "🇮🇸": "Icelandic",
    "🇮🇩": "Indonesian",
    "🇮🇶": "Iraqi Arabic",
    "🇮🇪": "Irish",
    "🇮🇹": "Italian",
    "🇯🇵": "Japanese",
    "🇬🇱": "Kalaallisut",
    "🇰🇷": "Korean",
    "🇱🇧": "Lebanese Arabic",
    "🇱🇾": "Libyan Arabic",
    "🇩🇿": "Maghrebi dialect",
    "🇲🇾": "Malay",
    "🇲🇽": "Mexican Spanish",
    "🇳🇴": "Norwegian",
    "🇮🇷": "Persian",
    "🇵🇱": "Polish",
    "🇵🇹": "Portuguese",
    "🇨🇦": "Quebec French",
    "🇷🇴": "Romanian",
    "🇷🇺": "Russian",
    "🇷🇸": "Serbian",
    "🇪🇸": "Spanish",
    "🇸🇩": "Sudanese Arabic",
    "🇸🇪": "Swedish",
    "🇵🇭": "Tagalog",
    "🇹🇭": "Thai",
    "🇹🇷": "Turkish",
    "🇺🇦": "Ukrainian",
    "🇵🇰": "Urdu",
    "🇻🇳": "Vietnamese",
}

LANG_TO_EMOJI = {v: k for k, v in LANG_EMOJIS.items()}

_all_langs = list(LANG_EMOJIS.items())

# Options for Select and Buttons with exact space styling requested
_OPTIONS_A = [discord.SelectOption(label=f"{e} {l}", value=e) for e, l in _all_langs[:25]]
_OPTIONS_B = [discord.SelectOption(label=f"{e} {l}", value=e) for e, l in _all_langs[25:]]

_SELECT_A_KEYS = set(e for e, _ in _all_langs[:25])
_SELECT_B_KEYS = set(e for e, _ in _all_langs[25:])

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

    response_text = generate(prompt)
    lines = response_text.strip().split("\n")
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

        # Row 0: Back Thought button
        bt_button = discord.ui.Button(
            label="Back Thought",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        bt_button.callback = self.bt_callback
        self.add_item(bt_button)

        # Row 1: Group A
        select_a = discord.ui.Select(
            placeholder="Group A",
            min_values=1,
            max_values=1,
            options=_OPTIONS_A,
            row=1
        )
        select_a.callback = self.selecta_callback
        self.add_item(select_a)

        # Row 2: Group B
        select_b = discord.ui.Select(
            placeholder="Group B",
            min_values=1,
            max_values=1,
            options=_OPTIONS_B,
            row=2
        )
        select_b.callback = self.selectb_callback
        self.add_item(select_b)

    def _build_display(self):
        display = []
        if "TRUTH" in self.selected_values:
            display.append("🔎 Reveals the Hidden Truth")
        for v in self.selected_values:
            if v != "TRUTH":
                display.append(f"{v} {LANG_EMOJIS[v]}")
        return ' + '.join(display) if display else 'None'

    def _update_lang(self, new_emoji, from_keys):
        prev = [v for v in self.selected_values if v not in from_keys]
        self.selected_values = prev + [new_emoji]

    async def bt_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        if "TRUTH" in self.selected_values:
            self.selected_values.remove("TRUTH")
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label == "Back Thought":
                    item.style = discord.ButtonStyle.secondary
        else:
            self.selected_values = ["TRUTH"] + [v for v in self.selected_values if v != "TRUTH"]
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label == "Back Thought":
                    item.style = discord.ButtonStyle.success
                    
        await interaction.response.edit_message(
            content=f"## [ \"TRANSLATER\". ] *\n**Message :** *{self.original_text[:80]}*\n\n**Selection :** {self._build_display()}\n\nConfirm",
            view=self
        )

    async def selecta_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        self._update_lang(interaction.data["values"][0], _SELECT_A_KEYS)
        await interaction.response.edit_message(
            content=f"## [ \"TRANSLATER\". ] *\n**Message :** *{self.original_text[:80]}*\n\n**Selection :** {self._build_display()}\n\nConfirm",
            view=self
        )

    async def selectb_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        self._update_lang(interaction.data["values"][0], _SELECT_B_KEYS)
        await interaction.response.edit_message(
            content=f"## [ \"TRANSLATER\". ] *\n**Message :** *{self.original_text[:80]}*\n\n**Selection :** {self._build_display()}\n\nConfirm",
            view=self
        )

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.success, row=3)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return

        if not self.selected_values:
            await interaction.response.send_message("⚠️ Please Select at least one Option first", ephemeral=True)
            return

        # Passe le menu privé en état de chargement
        await interaction.response.edit_message(content="⏳ Processing . . .", view=None)
        self.stop()

        values = self.selected_values
        has_truth = "TRUTH" in values
        lang_values = [v for v in values if v != "TRUTH"]
        translator = interaction.user.mention

        try:
            # Exécution de l'IA
            if not has_truth and len(lang_values) == 1:
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, result_text = process_translation(self.original_text, target_lang, "translate")

                if source_lang is None:
                    await self.message_ref.reply("❌ Language Not Enregistered")
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")
                if source_lang == target_lang:
                    reply = f"{source_emoji} *(Already in {source_lang}.)* {translator}"
                else:
                    reply = f"{source_emoji} {result_text}\nTranslated by {translator}"

            elif has_truth and len(lang_values) == 0:
                source_lang, result_text = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await self.message_ref.reply("❌ Language Not Enregistered")
                    return

                reply = f"{result_text}\nRevealed by {translator}"

            elif has_truth and len(lang_values) == 1:
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, truth_text = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await self.message_ref.reply("❌ Language Not Enregistered")
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")

                if source_lang == target_lang:
                    reply = f"{source_emoji} *(Already in {target_lang}.)* {translator}\n{truth_text}\nRevealed by {translator}"
                else:
                    _, translated_truth = process_translation(truth_text, target_lang, "translate")
                    reply = f"{source_emoji} {translated_truth}\nRevealed and Translated by {translator}"

            else:
                await self.message_ref.reply("❌ Invalid Combination")
                return

            # --- SUCCÈS : ENVOI DES MESSAGES ---
            
            # 1er message public : Unique message "Done ! ✅" dans le salon
            await self.message_ref.reply("Done ! ✅")
            
            # 2nd message public : La traduction juste après
            await self.message_ref.reply(reply)
            
            # Remet également le message "Done ! ✅" sur le volet éphémère privé de l'utilisateur
            await interaction.edit_original_response(content="Done ! ✅")

        except Exception as e:
            await self.message_ref.reply(f"❌ Error: {str(e)}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Cancelled", view=None)
        self.stop()


@bot.tree.context_menu(name="TRANSLATER")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content.strip():
        await interaction.response.send_message("❌ This Message is Not Compatible with the Application [ \"TRANSLATER\". ] *", ephemeral=True)
        return

    view = TranslateView(
        original_text=message.content,
        message_ref=message,
        invoker_id=interaction.user.id
    )

    await interaction.response.send_message(
        f"## [ \"TRANSLATER\". ] *\n**Message :** *{message.content[:80]}{'...' if len(message.content) > 80 else ''}*\n\nSelect at least one Option, then Confirm",
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
            
