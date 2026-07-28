# Describes one accepted argument of a registered capability.

uint8 TYPE_STRING=0
uint8 TYPE_INTEGER=1
uint8 TYPE_FLOAT=2
uint8 TYPE_BOOLEAN=3

string name
uint8 value_type
bool required
string description
string default_value
string[] allowed_values

