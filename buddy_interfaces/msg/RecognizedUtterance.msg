# Final or interim locally recognized speech.

uint8 INPUT_PUSH_TO_TALK=0
uint8 INPUT_WAKE_WORD=1
uint8 INPUT_TEST=2

std_msgs/Header header
unique_identifier_msgs/UUID utterance_id
string text
string locale
float32 confidence
bool is_final
uint8 input_mode

