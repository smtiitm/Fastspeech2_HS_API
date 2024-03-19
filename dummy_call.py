import requests
import json
import base64

url_text_dict = {

     "http://10.24.6.165:2001": "पहलगाम और अनंतनाग में तापमान माइनस",
     "https://asr.iitm.ac.in/tts/hindi/male": "पहलगाम और अनंतनाग में utkarsh तापमान माइनस",
    "http://10.24.6.165:2002": "पहलगाम और अनंतनाग में तापमान माइनस",
    "http://10.24.6.165:2003": "how are you?: english male",
    "http://10.24.6.165:2004": "how are you? english female",
    "http://10.24.6.165:2005": "உலகிற்கு பாரதம் வழிகாட்டும்: ஆர்எஸ்எஸ் தலைவர்",
    "http://10.24.6.165:2006": "உலகிற்கு பாரதம் வழிகாட்டும்: ஆர்எஸ்எஸ் தலைவர்",
    "http://10.24.6.165:2007": "స్ట్రేలియాతో జరిగిన తొలి టీ20లో భారత జట్టు థ్రిల్లింగ్ ",
    "http://10.24.6.165:2008": "స్ట్రేలియాతో జరిగిన తొలి టీ20లో భారత జట్టు థ్రిల్లింగ్",
    "http://10.24.6.165:2009": "ਨਵੰਬਰ ਨੂੰ ਨਗਰ ਕੀਰਤਨ ਦੇ ਮੱਦੇਨਜ਼ਰ ਟ੍ਰੈਫਿਕ ਪੁਲਿਸ ਨੇ ਸ਼ਹਿਰ ‘ਚ ਰੂਟ",
    "http://10.24.6.165:2010": "ਨਵੰਬਰ ਨੂੰ ਨਗਰ ਕੀਰਤਨ ਦੇ ਮੱਦੇਨਜ਼ਰ ਟ੍ਰੈਫਿਕ ਪੁਲਿਸ ਨੇ ਸ਼ਹਿਰ ‘ਚ ਰੂਟ",
    "http://10.24.6.165:2011": "طویل مذاکرات کے بعد جمعے کی صبح مقامی ",
    "http://10.24.6.165:2012": "طویل مذاکرات کے بعد جمعے کی صبح مقامی",
    "http://10.24.6.165:2013": "हॅलो",
    "http://10.24.6.165:2014": "हॅलो" ,
    "http://10.24.6.165:2015": "હલો",
    "http://10.24.6.165:2016": "હલો",
    "http://10.24.6.165:2017": "হ্যালো",
    "http://10.24.6.165:2018": "হ্যালো",
    "http://10.24.6.165:2019": "হ্যালো",
    "http://10.24.6.165:2020": "হ্যালো",
    "http://10.24.6.165:2022": "हॅलो",

    "http://10.24.6.165:2023": "ಹಲೋ",
    "http://10.24.6.165:2024": "ಹಲೋ",
    "http://10.24.6.165:2025": "ഹലോ",
    "http://10.24.6.165:2026": "ഹലോ",
    "http://10.24.6.165:2027": "হ্যালো",
    "http://10.24.6.165:2028": "হ্যালো",
    "http://10.24.6.165:2029": "ହେଲୋ",
    "http://10.24.6.165:2030": "ହେଲୋ",
    "http://10.24.6.165:2031": "हॅलो",
    "http://10.24.6.165:2032": "हॅलो"

}
#text = "हम इस परीक्षण को keshav Agrwal के लिए कर रहे हैं और उम्मीद है कि यह सही हो जाएगा।"
#url = "http://10.24.6.165:2001"
for url, text in url_text_dict.items():
    payload = json.dumps({
    "input": text,
    "alpha": 1,
    "segmentwise":"True"
    })
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Check for any HTTP errors

        # Parse the response as JSON
        response_data = response.json()

        # Check if the 'audio' key exists in the response
        if 'audio' in response_data:
            audio = response_data['audio']
            file_name = f"{url.replace(':', '_').replace('/', '_')}.mp3"
            with open(file_name, 'wb') as wav_file:
                decoded_string = base64.b64decode(audio)
                wav_file.write(decoded_string)
            print(f"Audio file {file_name} saved successfully.")
        else:
            print(response_data["reason"])

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"An error occurred during the request: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"JSON decoding error: {json_err}")
    except Exception as err:
        print(f"An unexpected error occurred: {err}")
