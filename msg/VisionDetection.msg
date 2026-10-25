# VisionDetection.msg
builtin_interfaces/Time stamp
string camera_id
string[] detected_classes     # "person", "smoke", "fire", "motion"
float64[] confidences
bool intrusion_confirmed
bool visual_fire_confirmed
string bounding_boxes_json
