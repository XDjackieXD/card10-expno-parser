# Diagnosis Key Matching for CARD10 Exposure Notification Data

Run `./match_data.sh exno.bin` where `exno.bin` is the file written by my patched version of the ExpNo-CARD10-App (see [this comment on Schneider's merge request](https://git.card10.badge.events.ccc.de/card10/firmware/-/merge_requests/392#note_7594) for details).
Currently only data from Austria is used for matching and I can't guarantee that all matches are really found (I tested this with RPIs I created myself to match some of the published diagnosis keys but the used tool has quite a few parameters I don't fully understand :P).

Feel free to clean this up as the code is very hacky at the moment.
