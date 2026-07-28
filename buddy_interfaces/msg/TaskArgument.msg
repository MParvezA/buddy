# A typed task argument. The value is encoded as text and parsed according to
# value_type using the registered capability schema.

uint8 TYPE_STRING=0
uint8 TYPE_INTEGER=1
uint8 TYPE_FLOAT=2
uint8 TYPE_BOOLEAN=3

string name
uint8 value_type
string value

