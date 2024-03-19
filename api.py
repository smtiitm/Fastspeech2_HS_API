
#Default Imports
import os
import io
import base64
import re
import traceback
from flask import Flask, request, jsonify
from scipy.io.wavfile import write
import sys
import torch
from espnet2.bin.tts_inference import Text2Speech
import time
from webvtt import WebVTT, Caption, read_buffer
from io import StringIO
import json
import yaml
import logging
from datetime import datetime

#Hifigan Path
sys.path.append("hifigan")


#User based Imports
from meldataset import MAX_WAV_VALUE
from env import AttrDict
from models import Generator
from text_preprocess_for_inference import TTSDurAlignPreprocessor, CharTextPreprocessor,TTSPreprocessor, TTSDurAlignPreprocessor_VTT, CharTextPreprocessor_VTT, TTSPreprocessor_VTT
#from text_preprocess_for_inference_parallel import TTSDurAlignPreprocessor, CharTextPreprocessor,TTSPreprocessor
from inference_new import text_synthesis

# Configure the logging
log_file_path = "api_logs.log"
logging.basicConfig(filename=log_file_path, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(funcName)s - Line %(lineno)d - %(message)s')

root_logger = logging.getLogger()

# Set the level of the root logger
root_logger.setLevel(logging.ERROR)
app = Flask(__name__)

#Language and gender from PORT
language = os.environ.get('LANGUAGE') 
gender = os.environ.get('GENDER') 

# language = "hindi" 
# gender = "male"

# Initialize your models as global variables for vocoder models, fastspeech2 models, and phone dictionary
vocoder_models = {}  # Dictionary to store vocoder models
fastspeech2_models = {}
phone_dictionary = {}

# Function to load HiFi-GAN vocoder model
def load_hifigan_vocoder(language, gender, device):
    #Load HiFi-GAN vocoder configuration file and generator model for the specified language and gender
    vocoder_config = f"vocoder/{gender}/aryan/hifigan/config.json"
    vocoder_generator = f"vocoder/{gender}/aryan/hifigan/generator"
    #Read the contents of the vocoder configuration file
    with open(vocoder_config, 'r') as f:
        data = f.read()
    json_config = json.loads(data)
    h = AttrDict(json_config)
    torch.manual_seed(h.seed)
    #Move the generator model to the specified device (CPU or GPU)
    device = torch.device(device)
    generator = Generator(h).to(device)
    state_dict_g = torch.load(vocoder_generator, device)
    generator.load_state_dict(state_dict_g['generator'])
    generator.eval()
    generator.remove_weight_norm()

    #Return the loaded and prepared HiFi-GAN generator model
    return generator

# Function to load FastSpeech2 model
def load_fastspeech2_model(language, gender, device):
    with open(f"{language}/{gender}/model/config.yaml", "r") as file:
              
        config = yaml.safe_load(file)
    
    # Set paths for feature statistics
    current_working_directory = os.getcwd()
    feat="model/feats_stats.npz"
    pitch="model/pitch_stats.npz"
    energy="model/energy_stats.npz"
    
    feat_path=os.path.join(current_working_directory,language,gender,feat)
    pitch_path=os.path.join(current_working_directory,language,gender,pitch)
    energy_path=os.path.join(current_working_directory,language,gender,energy)

    # Update paths in the configuration
    config["normalize_conf"]["stats_file"]  = feat_path
    config["pitch_normalize_conf"]["stats_file"]  = pitch_path
    config["energy_normalize_conf"]["stats_file"]  = energy_path
        
    with open(f"{language}/{gender}/model/config.yaml", "w") as file:
        yaml.dump(config, file)
    
    # Set paths for the FastSpeech2 model
    tts_model = f"{language}/{gender}/model/model.pth"
    tts_config = f"{language}/{gender}/model/config.yaml"
    
    # Load the FastSpeech2 model and store it in the global variable
    fastspeech2_model = Text2Speech(train_config=tts_config, model_file=tts_model, device=device)
    
    # Store the loaded model in the dictionary
    fastspeech2_models[(language, gender)] = fastspeech2_model
    return fastspeech2_model

# Dictionary that maps languages to GPU indices. Load more languages accordingly.
language_to_gpu = {
    "hindi": "cuda:0",
    "tamil":"cuda:1",
    "telugu":"cuda:6",
    "marathi":"cuda:1",
    "gujarati":"cuda:1",
    "assamese":"cuda:2",
    "bengali":"cuda:2",
    "bodo":"cuda:2",
    "kannada":"cuda:2",
    "malayalam":"cuda:3",
    "manipuri":"cuda:3",
    "odia":"cuda:3",
    "rajasthani":"cuda:4",
    "english":"cuda:5",
    "punjabi":"cuda:4",
    "urdu": "cuda:4",  
}
SAMPLING_RATE = 22050

# API route to convert VTT to speech
@app.route('/vtt_to_speech', methods=['GET', 'POST'], strict_slashes=False)
def extract_text_from_vtt():
    global vocoder_models  
    global fastspeech2_models
    global gender
    global phone_dictionary
    try:
      
        json_data = request.get_json()
        vtt_content = json_data.get("input")
        alpha = json_data.get("alpha", 1)
        if not alpha:
            alpha = 1
        #print(vtt_content)
        if not vtt_content:
            return jsonify(status='failure', reason='Missing or empty "vtt_content" in the request JSON.')

        # Read VTT content
        vtt = read_buffer(StringIO(vtt_content))
        segments = [caption.text for caption in vtt.captions]
        
        # Concatenate all segments into a single text string
        extracted_text = segments
        if language == "urdu" or language == "punjabi":
            preprocessor = CharTextPreprocessor_VTT()
            preprocessed_text, phrases = preprocessor.preprocess(extracted_text, language, gender)
            
        elif language == "english":
            preprocessor = TTSPreprocessor_VTT()
            preprocessed_text, phrases, phone_dictionary = preprocessor.preprocess(extracted_text, language, gender, phone_dictionary)
        
        else:
            preprocessor = TTSDurAlignPreprocessor_VTT()
     
            preprocessed_text, phrases, phone_dictionary = preprocessor.preprocess(extracted_text, language, gender, phone_dictionary)
        #preprocessed_text = " ".join(preprocessed_text)
        #print(phone_dictionary.keys())
        # Get the GPU number based on the language
        device = language_to_gpu.get(language, "cpu")
     
        # Load models based on the predefined language and gender
        if (language, gender) not in vocoder_models:
            vocoder = load_hifigan_vocoder(language, gender, device)
            vocoder_models[(language, gender)] = vocoder
        else:
            vocoder = vocoder_models[(language, gender)]

        if (language, gender) not in fastspeech2_models:
            fastspeech2 = load_fastspeech2_model(language, gender, device)
        
        else:
            fastspeech2 = fastspeech2_models[(language, gender)]
        
        # Synthesize audio from preprocessed text using the loaded models
       # audio = text_synthesis(language, gender, preprocessed_text, vocoder, fastspeech2, MAX_WAV_VALUE, device)
        # avoid saving file on disk
        # output_stream = io.BytesIO()
        # write(output_stream, SAMPLING_RATE, audio)
        # audio_wav_bytes = base64.b64encode(output_stream.getvalue())
        # return jsonify(status="success", audio=audio_wav_bytes.decode('utf-8'))
        audio_segments_wav_bytes = []
        for text in preprocessed_text:
            text = " ".join(text)
            #print("text", text)
            # Synthesize audio from preprocessed text using the loaded models
            audio = text_synthesis(language, gender, text, vocoder, fastspeech2, MAX_WAV_VALUE, device, alpha)

            # avoid saving file on disk
            output_stream = io.BytesIO()
            write(output_stream, SAMPLING_RATE, audio)
            audio_wav_bytes = base64.b64encode(output_stream.getvalue())
            audio_segments_wav_bytes.append(audio_wav_bytes.decode('utf-8'))
        
        return jsonify(status="success", segments=audio_segments_wav_bytes)
    except Exception as err:
        # Log the error along with the client's IP address
        logging.error(f"Exception occurred: {err}. Input text: {extracted_text}")
        return jsonify(status="failure", reason = "Error due to language-port mismatch: Language given is- " + str(err) + "and language on port is- " + language)
    
@app.route('/', methods=['GET', 'POST'], strict_slashes=False)
def synthesize():
    global vocoder_models  
    global fastspeech2_models
    global language
    global gender
    global phone_dictionary
    
   
    try:
        json_data = request.get_json() 
        text = json_data["input"]
        alpha = json_data.get("alpha", 1)
        if not alpha:
            alpha = 1
       
        if not isinstance(text, str):
            input_type = type(text)
            # Log the error
            logging.error(f"Unsupported input type {input_type}. Input text should be in string format. Input text: {text}")
            return jsonify(status='failure', reason=f"Unsupported input type {input_type}. Input text should be in string format.") 

               
        if language == "urdu" or language == "punjabi":
            preprocessor = CharTextPreprocessor()
            preprocessed_text, phrases = preprocessor.preprocess(text, language, gender)
            
        elif language == "english":
            preprocessor = TTSPreprocessor()
            preprocessed_text, phrases, phone_dictionary = preprocessor.preprocess(text, language, gender, phone_dictionary)
        
        else:
            preprocessor = TTSDurAlignPreprocessor()
            preprocessed_text, phrases, phone_dictionary = preprocessor.preprocess(text, language, gender, phone_dictionary)
        preprocessed_text = " ".join(preprocessed_text)

        print(preprocessed_text)
        # Get the GPU number based on the language
        device = language_to_gpu.get(language, "cpu")
        print(device)
        # Load models based on the predefined language and gender
        if (language, gender) not in vocoder_models:
            vocoder = load_hifigan_vocoder(language, gender, device)
            vocoder_models[(language, gender)] = vocoder
        else:
            vocoder = vocoder_models[(language, gender)]

        if (language, gender) not in fastspeech2_models:
            fastspeech2 = load_fastspeech2_model(language, gender, device)
        
        else:
            fastspeech2 = fastspeech2_models[(language, gender)]
        
        # Synthesize audio from preprocessed text using the loaded models
        audio = text_synthesis(language, gender, preprocessed_text, vocoder, fastspeech2, MAX_WAV_VALUE, device, alpha)

        # avoid saving file on disk
        output_stream = io.BytesIO()
        write(output_stream, SAMPLING_RATE, audio)
        audio_wav_bytes = base64.b64encode(output_stream.getvalue())
        return jsonify(status="success", audio=audio_wav_bytes.decode('utf-8'))
        
    except Exception as err:
        
        tb = traceback.extract_tb(err.__traceback__)
        last_frame = tb[-1]

        logging.error(f"Exception occurred: {err}.|| TRACEBACK : Error in File {last_frame.filename}, Line {last_frame.lineno} Error {type(err).__name__} : {str(err)}")
        # Log the error along with the client's IP address
        #logging.error(f"Exception occurred: {err}. Input text: {text}")
        return jsonify(status="failure", reason = "Error due to language-port mismatch: Language given is- " + str(err) + "and language on port is- " + language)
    
if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5002, debug = True)