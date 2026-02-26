## Conversion Options

### Profiles

The profile affects how messages are formatted. In most cases, **Auto-detect profile** (in Settings) works best.

- **Group Chat:** Standard formatting for multi-user chats.
- **Personal Chat:** Formats the conversation from the perspective of "Me" and "Partner". You can set custom names for these roles.
- **Channel:** Simplified format suitable for channel posts.
- **Posts and Comments:** A special mode for channels where comments are enabled. It treats the first message as the main post and subsequent messages as replies.

  **How to use:**
  1. Create your own group chat in Telegram
  2. Find the post in the channel whose comments you want to export
  3. Starting from the topmost comment (which is the post), select all comments down to the desired bottommost one
  4. **Important:** Do not exceed 100 selected messages, otherwise the topmost ones will disappear from selection and you'll need to start over
  5. Forward the selected messages to your group chat
  6. Export this chat through Telegram

  **Benefits:** This method allows you to avoid downloading the entire channel just for a few hundred messages under a post. Although user reactions under messages are lost from context, this is much more efficient than downloading millions of messages for just a couple hundred.

### Key Options

- **Show reactions:** Includes message reactions (e.g., 👍 2).
- **Optimization:** A mode for channels that groups consecutive messages from the same author to save tokens.

### Anonymization

The anonymization module lets you hide or mask personal data before export or before sending a chat to an LLM: participant names and links.

- **Enabling:** Open the **Anonymization** dialog from the UI and turn anonymization on. Settings are saved and applied on convert and export.
- **Names:** When name hiding is on, display names are replaced by a mask. The mask format is configurable (e.g. `[NAME {index}]` or `User {index}`), where `{index}` is the participant’s index. You can add custom rules for specific names.
- **Links:** Links in messages can be hidden or replaced with a single placeholder, show domain only, use indexed placeholders (`[LINK 1]`, `[LINK 2]`, etc.), or a custom format. Presets and custom filters by domain or regex are available.
- **Presets:** Save sets of options (name format, link format, filters) as presets and switch between them as needed.
- **CLI:** Anonymization is configured via the JSON config: an `anonymization` section with `enabled`, `hide_links`, `hide_names`, `name_mask_format`, `link_mask_mode`, `link_mask_format`, and optionally `custom_names`, `custom_filters`. See the CLI documentation for details.
