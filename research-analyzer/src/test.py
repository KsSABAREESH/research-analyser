import google.generativeai as genai

genai.configure(api_key="AIzaSyD6ronWXz8Gj8I-XpOmlprQT7WgD1jbefU")

# List all available models for your key
for model in genai.list_models():
    print(model.name)
