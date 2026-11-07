# Changelog

Neueste Version oben. Der Abschnitt einer Version wird beim Veröffentlichen als Release-Notiz übernommen und
erscheint in der App unter „What's new“. **Einträge auf Englisch.** **Die erste Zeile erscheint in der
Update-Karte der App** – kurz und für Nutzer formulieren.

## 2.10.1
The word and sentence highlight now sit exactly on the text again.

- **Fix:** when the reading font finished loading after the text was shown, the highlights could sit a few pixels
  off – they now follow the font

## 2.10.0
A new look for the logo – and a fresh start button when recording your own voice.

- **New logo:** a dark tile with light bars – in the Dock, in the sidebar and on the welcome screen (in the app the
  bars follow your accent color). It no longer moves, and the Dock icon stays the same whether the app is open or not
- **Your own voice:** while recording, **Start over** discards the take and begins again right away
- **Export:** after saving, the dialog closes so you can see the confirmation
- **Player:** when the follow-along line appears, the sidebar footer grows exactly with the player
- **Safer:** only the Vorleser window can control the app – other websites can no longer reach it
- **Under the hood:** the interface is split into smaller files, and every build uses the same tested package versions

## 2.9.1
Cleaner highlighting and steadier dragging.

- **Highlighting:** the spoken sentence gets one rounded area per line – no square line starts, no overlap
- **Progress bar:** dragging no longer selects text, and clicking doesn't leave a focus ring
- **Sidebar:** the footer is as tall as the player, so their lines meet
- **Updates:** a partial update shows its small size right from the start

## 2.9.0
Every move has a direction now – and a live preview of your colors.

- **Navigation:** content moves the way the sidebar is laid out: a text further down slides in from below, Settings
  from below, New text from above; tabs slide sideways and their underline stretches; editing a text zooms in and
  back out. The old content glides away instead of vanishing
- **Settings › Appearance:** a small preview of the whole app that changes with mode and accent color
- **More room:** the player and the follow-along line are more compact; the Settings header is frosted glass and
  the content scrolls beneath it
- **Calmer sidebar:** hovering and the open text are simply shaded, like in all menus; in the voice menu the
  shading covers the whole row

## 2.8.2
A new glass look – and from now on, updates download only what changed.

- **Glass look:** the player and the bar at the top of the text are frosted glass across the full width; text and
  settings scroll behind them. Menus, tooltips, dialogs, the tour and the update card share the same glass – with
  calmer, less rounded shapes
- **Sidebar:** a glass highlight glides to the entry under the mouse, stays on the open text and presses in briefly
  when you click – edge to edge
- **Smaller updates:** instead of the whole app (~260 MB), updates now load only the changed files (usually around
  15 MB). Every other file is checked first; if anything doesn't match, the full update is downloaded as before.
  Takes effect from the next update on
- **Storage:** when the sizes are ready, the cards no longer briefly disappear and float in again – their height
  glides and only the values fade in
- **About:** the bubble at Simon's name shows GitHub and LinkedIn side by side

## 2.7.1
Smoother follow-along line, and Simon's name now leads to GitHub or LinkedIn.

- **Follow along:** the sentence line drops in from above when you leave the text and rises away when you go back;
  after dragging the progress bar there is no extra sentence change any more
- **About:** clicking "Simon Schnetzer" (Settings › App, tour) opens a small bubble with GitHub and LinkedIn
- **Expanding sections** (e.g. "What gets sent?" in "Report a problem") now open and close smoothly
- **What's new:** nothing is pre-selected when it opens

## 2.7.0
Follow along from anywhere: the spoken sentence now shows above the player – and a new "Playback" tab.

- **Follow along:** outside the text page (Settings, New text), the current sentence appears above the player with
  the gliding word marker; long sentences slide along, the next sentence rises in
- **Progress bar:** while dragging, a frame marks the target word – in the text and in the sentence above the player;
  after a paused jump the marker stays on that word instead of the first one
- **Settings › Playback:** new tab for "Generate ahead", "Highlight while reading" and the preview
- **Prepared:** the bar shows ready sections even after a gap, and the status line counts all of them
  ("… · next one still missing")
- **Player title:** "Jump to text" tooltip; not a link while you're already on the text page
- **Own voice:** the install bar no longer jumps between 97 % and 100 % at the end; favorite stars no longer flash
  while a voice is getting ready
- **Icon:** same mark as the logo in the app; on the Mac the Dock icon follows your accent color

## 2.6.0
A smoother progress bar, a "What's new" overview after every update – and Vorleser is now marked as beta.

- **Progress bar:** lands exactly where you click, can be dragged, snaps to chapter starts, shows chapter and
  section before you click, and glides to its new position instead of jumping
- **Generate ahead:** new setting (Settings › Appearance) for how much is generated in advance – minimal, normal,
  more (10 sections) or the whole text in the background; playback still starts as soon as the current section is ready
- **Voice menu:** shows for each voice how much of the current text is already generated
- **What's new:** after an update, a card shows what changed; all versions are listed under Settings › App ›
  What's new (or click "BETA")
- **Beta:** Vorleser is marked as beta in the app and on the website
- **Own voice:** a newly recorded voice briefly pulses in the list and shows "getting ready" until it can be used;
  the record dialog no longer shifts while the timer runs
- **Sidebar:** "Report a problem" now sits above "Settings"

## 2.5.4
Storage and library now always show the same state – and you can see who makes Vorleser.

- **Storage:** deleted audio no longer briefly reappears; the "prepared" bar in the sidebar now always matches
  the player
- **About Vorleser:** developer's name in Settings › App, in the tour and in "Report a problem"; copyright in the
  Finder info window and in the Windows file properties

## 2.5.3
Your own voice now reads about 2.5 times faster (Mac with Apple chip).

- **Own voice:** faster on the Mac with the same quality; the voice sample is processed only once

## 2.5.2
New versions are now announced within minutes instead of hours.

- **Updates:** the app checks for a new version every minute – no limit even with many users on the same network

## 2.5.0
New export: three clear steps to your audiobook – with progress per chapter and time remaining.

- **Export:** pick a format (with size estimate, M4B recommended) → progress per chapter with time remaining →
  finished file with "Save"
- **In the background:** "Continue in background" only closes the dialog; the library shows the progress, and a
  notice tells you when the audiobook is ready
- **Animations:** the dialog resizes smoothly; when it finishes, a check mark draws itself and a sound wave pops up

## 2.4.0
Smoother transitions – texts, player and export now move gently instead of jumping.

- **Library:** new texts visibly land at the top, deleted ones slide out (own voices too)
- **Player:** slides in from below when you open a text and out again when you edit it
- **Export:** progress fades in; when done, a check mark, a green bar and a download button that pops in
- **Update:** after "Update", the card smoothly turns into the progress bar
- **Details:** the drop zone lifts while dragging a file, the "detected" hint pops up, prepared sections fade in
  their marking, the sidebar slides in with a dimmed background in narrow windows

## 2.3.9
Vorleser is now open source – free software under GPL-3.0.

- **Open source:** source code on GitHub, linked under *Settings › App › Open Source*
- **Licenses:** the license text and notices for all bundled components ship with the app

## 2.3.8
Updates download in the background – you decide when to restart.

- **Updates:** are detected reliably right after launch (the notice sometimes appeared only after 30 minutes)
- **Update ready:** "Restart now" or "Later" – then the new version runs the next time you open Vorleser
- **Fast restart:** the new version is unpacked in advance; restarting takes under a second instead of about ten
- **Status line:** no more flickering; new text slides in briefly
- **Sidebar:** more space between "New text" and "Library"
- **Progress:** the library shows the same state as the player and updates live while you listen
- **Voices:** language, filter and search in one row

## 2.3.6
Polish: no white flash on launch, a separate "App" tab, storage loads visibly.

- **Dark mode:** the window no longer flashes white on launch, also with "Appearance: System"
- **Settings:** "Storage" and "App" are separate tabs
- **Storage:** placeholders until sizes are calculated; when reopened, the last values appear instantly
- **All prepared:** no longer looks like a button; hints match the current state
- **Sidebar:** bottom divider aligned with the player bar, "Report a problem" spelled out, search only from
  7 texts, each text's bar shows in a lighter shade what is already prepared

## 2.3.5
Tidied up: the App section in Settings, and the app no longer opens twice.

- **Settings › App:** one row per action with a short explanation, version at the top right, uninstall set apart
- **No second window:** if Vorleser is started again (e.g. a second copy of the app), it brings the existing
  window to the front instead of opening another one

## 2.3.4
New: reading and preparing keep running in the background – the player is always visible.

- **Player everywhere:** playback continues when you switch to Settings or "New text"; the player bar stays at
  the bottom, and clicking the title takes you back to the text
- **In the background (Mac):** reading continues when the window is hidden or the app isn't in front
- **Prepare in advance:** keeps running in the background (progress ring in the library, notice when done) and
  lets reading go first; cancel with its own ✕ instead of accidentally clicking the button
- **"Prepared" is consistent:** button, status line, bar and the marking in the text all show the same
- **Record own voice:** the buttons no longer shift
- **Quitting with ⌘Q:** no more background processes left running
- **Installing your own voice:** the model download starts immediately (previously "0 MB" for over a minute); it
  starts with "getting ready" instead of "slow connection"; the card no longer jumps in height

## 2.3.3
Polish: calmer animations in the tour and while installing your own voice.

- **Tour:** the hint card is in the right place from the start; spotlight and card glide more smoothly
- **Install own voice:** at the end "Almost done – setting up the voice model" instead of a seemingly endless
  download; the shimmer in the bar no longer jumps; the card dissolves at the end and the content moves up softly
- **Own voice:** recording opens right after installation; the name is only a suggestion; the new voice's preview
  is prepared in the background right away (reading takes priority)

## 2.3.2
Fixed: updates are found on the Mac again.

- **Mac:** the automatic update check had been failing since 2.1.0. If you have 2.1.0 to 2.3.1, install this
  version once by hand from the download page – after that, updates arrive automatically again.
- **Record own voice:** the text to read is fully visible without scrolling

## 2.3.1
New: Vorleser can be uninstalled directly from the app.

- **Uninstall:** Settings › Storage & App – shows what will be deleted beforehand and asks twice. Texts and own
  voices can be kept if you like.
- **Windows:** when removing via "Apps", Vorleser asks whether your data should be deleted too.

## 2.2.0
New: clean up storage selectively – per text, previews, leftovers, exports and models.

- **Storage:** overview of what takes up how much space; delete individual parts instead of only "Clear all"
- **Deleting a text** now also removes its generated audio
- **Tour:** the sample text stays in the library afterwards (even if cancelled), without copies on a repeated tour
- **Record own voice:** text in the interface language, with a Deutsch | English switch
- **Installing your own voice:** three alternating scenes for the voice model (waveform › network › speech
  bubble); the total size stays fixed at 3,060 MB
- **English interface:** numbers formatted correctly (1,404 MB instead of 1.404 MB)
- **Update check:** within a few seconds of every launch

## 2.1.0
New: report problems directly from the app, and a clearer installation of your own voice.

- **Report a problem:** bug icon at the bottom left (or Settings › Storage & App) – describe it, done.
- **Own voice:** one "Use your own voice" button; the installation now shows size, speed, time remaining and
  what's happening. Cancelling works reliably.
- **Follow along:** the word marking stays visible when the mouse is over it; no longer runs ahead with the
  offline voice.
- **Windows:** EPUB files can be imported again.
- **Updates** are found even when GitHub is receiving a lot of requests.

## 2.0.0
First desktop version for macOS (Apple chip) and Windows 10/11.

- Its own app window instead of a browser, installed with a double-click
- Own voice as an optional download directly from the app
- Automatic updates with one click
