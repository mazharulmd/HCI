# Lab runbook: running a CLEAR study session

This is the practical companion to `protocol.md`. Do not start data collection
until the ethics committee has approved the study and the protocol has been
pre-registered (for example on OSF).

## 1. Before the first participant (once)

1. **Fill in the study details** in `clear/ui/static/study_config.js`: PI name
   and e-mail, ethics reference and contact, compensation, retention period and
   withdrawal date. The start page shows a red warning while any `[placeholder]`
   is left.
2. **Choose the server computer.** One computer (the experimenter's) runs the
   server. All lab computers connect to it over the lab network, so that
   assignment and logs live in one place.
   ```bash
   git clone https://github.com/mazharulmd/HCI.git && cd HCI
   python -m pip install -r requirements.txt
   python -m pytest -q                       # all tests should pass
   python -m clear.ui.server --host 0.0.0.0 --port 8765
   ```
   Find the server's address on the lab network (`ipconfig` on Windows,
   `ip addr` on Linux, System Settings > Network on macOS), for example
   `192.168.1.20`. If the lab computers cannot connect, allow port 8765 in the
   server computer's firewall. The traffic stays inside the lab network; do not
   expose the server to the internet.
3. **Prepare each lab computer.** Use a recent Chrome, Edge or Firefox, at a
   screen width of at least 1280 pixels. Open
   `http://192.168.1.20:8765/start.html` (with your server's address) and
   bookmark it.
4. **Run pilots.** Run 5–10 pilot sessions with codes starting with `PILOT`
   (for example `PILOT01`). Pilot sessions use the same flow but are never
   analysed. Fix anything confusing **before** the first real participant, and
   note any change in the protocol's deviations section.
5. **Prepare a session sheet** that maps participant codes (`P001`, `P002`, ...)
   to session times. It must not contain names: keep names and payment records
   on a separate, access-controlled list.

## 2. Each session (about 35 minutes)

1. Greet the participant and seat them at a lab computer showing `start.html`.
2. Enter the participant's code and click **Begin session**, then hand over the
   computer. From here on, everything happens in the browser:
   consent → demographics → introduction → 2 practice tasks → 16 tasks with
   2 attention checks → questionnaire → debriefing.
3. Stay available for questions about *how to use* the interface. Do not give
   hints about which actions to approve. Use the same neutral wording for
   everyone, for example: "Please decide as you would with your own account."
4. If a participant declines consent, thank them; nothing beyond the refusal is
   recorded.
5. When the debriefing page appears, pay the participant and remind them not to
   tell others which tasks contained attacks.

You stay blind to condition: the console does not show it, and the status
page does not list conditions per participant.

**If something goes wrong** (browser closed, crash): open `start.html` again
and enter the **same** code. The participant keeps their condition, but the
tasks restart. Only the last attempt is analysed, and the number of restarts is
reported. Write the incident on the session sheet. A session with fewer
than 16 logged tasks is excluded as a technical failure (protocol section 4).

## 3. During data collection

* **Progress.** On the server computer, open
  `http://127.0.0.1:8765/api/status`. It shows how many participants are
  assigned per stratum and condition, and how many tasks each participant has
  finished. It answers only on the server computer itself.
* **Back-ups.** Copy the `user_study_logs/` folder to secure institutional
  storage at the end of every session day. It holds one `.jsonl` file per
  participant, `assignments.json` and `allocation.json`. Never edit or delete
  these files by hand.
* **Withdrawal.** If a participant withdraws, move their `.jsonl` file out of
  `user_study_logs/` into a separate folder and record the withdrawal. Do not
  delete their entry in `assignments.json`, because that would change the
  allocation records.

## 4. After the last participant

```bash
python experiments/analyze_user_study.py --logs user_study_logs --out results/user_study
```

The script writes `participants.csv` (one row per participant, with any
exclusion reason), `trials.csv`, `dialogs.csv`, `descriptives.csv`,
`primary_gee.csv`, `primary_permutation.csv`, `robustness_gee.csv`,
`noninferiority.csv` and `summary.json`. Report every pre-registered analysis,
whatever its outcome. Before sharing the data, remove the free-text answers if
they could identify anyone.
