# plugin-wake-word-precise
Use Mycroft Precise tflite models as your wake word.

This module provides a Mycroft plugin module for the hotword_factory which supports the `hey_mycroft.tflite` model. It adds a dependency for the tensorflow lite runtime, but other than that its requirements should be satisfied by the default Mycroft environment. 

## Installation

This module must be pip installed into the Mycroft virtual environment before use. 

```
mycroft-pip install https://github.com/MycroftAI/plugin-wake-word-precise
```

Then change your Mycroft Configuration to use the installed module:
```
        "module": "hotword_precise_lite",
        "local_model_file": "/path/to/your/model/hey_mycroft.tflite",
```

The Voice Service will automatically reload when you save the configuration. Check the output at `/var/log/mycroft/voice.log` to ensure the plugin and model were both loaded correctly.
