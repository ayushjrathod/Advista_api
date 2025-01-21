import asyncio

from groq import AsyncGroq
from sentence_transformers import SentenceTransformer

# This model supports two prompts: "s2p_query" and "s2s_query" for sentence-to-passage and sentence-to-sentence tasks, respectively.
# They are defined in `config_sentence_transformers.json`

import yt_dlp

def download_youtube_video(url, output_path):

    try:
        ydl_opts = {
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',  # Output path and filename template
            'format': 'bestvideo+bestaudio/best',  # Download the best available quality
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"Downloaded video from '{url}' successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

'''Example usage
    video_url = "https://www.youtube.com/watch?v=L8ypSXwyBds&t=1046s"
    output_path = "./demo video3.mp4"  # Specify your desired output path
    download_youtube_video(video_url, output_path)
'''
import os
from groq import Groq

# Initialize the Groq client
client = Groq()

# Specify the path to the audio file
filename = os.path.dirname(__file__) + "/sample_audio.m4a" # Replace with your audio file!

# Open the audio file
with open(filename, "rb") as file:
    # Create a translation of the audio file
    translation = client.audio.translations.create(
      file=(filename, file.read()), # Required audio file
      model="whisper-large-v3", # Required model to use for translation
      prompt="Specify context or spelling",  # Optional
      response_format="json",  # Optional
      temperature=0.0  # Optional
    )
    # Print the translation text
    print(translation.text)
# Understanding Metadata Fields
# When working with Groq API, setting response_format to verbose_json outputs each segment of transcribed text with valuable metadata that helps us understand the quality and characteristics of our transcription, including avg_logprob, compression_ratio, and no_speech_prob.

# This information can help us with debugging any transcription issues. Let's examine what this metadata tells us using a real example:


# {
#   "id": 8,
#   "seek": 3000,
#   "start": 43.92,
#   "end": 50.16,
#   "text": " document that the functional specification that you started to read through that isn't just the",
#   "tokens": [51061, 4166, 300, 264, 11745, 31256],
#   "temperature": 0,
#   "avg_logprob": -0.097569615,
#   "compression_ratio": 1.6637554,
#   "no_speech_prob": 0.012814695
# }

query_prompt_name = "s2p_query"
queries = [
    "What are some ways to reduce stress?",
    "What are the benefits of drinking green tea?",
]
# docs do not need any prompts
docs = [
    "There are many effective ways to reduce stress. Some common techniques include deep breathing, meditation, and physical activity. Engaging in hobbies, spending time in nature, and connecting with loved ones can also help alleviate stress. Additionally, setting boundaries, practicing self-care, and learning to say no can prevent stress from building up.",
    "Green tea has been consumed for centuries and is known for its potential health benefits. It contains antioxidants that may help protect the body against damage caused by free radicals. Regular consumption of green tea has been associated with improved heart health, enhanced cognitive function, and a reduced risk of certain types of cancer. The polyphenols in green tea may also have anti-inflammatory and weight loss properties.",
]

# ！The default dimension is 1024, if you need other dimensions, please clone the model and modify `modules.json` to replace `2_Dense_1024` with another dimension, e.g. `2_Dense_256` or `2_Dense_8192` !
# on gpu
model = SentenceTransformer("dunzhang/stella_en_400M_v5", trust_remote_code=True).cuda()
# you can also use this model without the features of `use_memory_efficient_attention` and `unpad_inputs`. It can be worked in CPU.
# model = SentenceTransformer(
#     "dunzhang/stella_en_400M_v5",
#     trust_remote_code=True,
#     device="cpu",
#     config_kwargs={"use_memory_efficient_attention": False, "unpad_inputs": False}
# )
query_embeddings = model.encode(queries, prompt_name=query_prompt_name)
doc_embeddings = model.encode(docs)
print(query_embeddings.shape, doc_embeddings.shape)
# (2, 1024) (2, 1024)

similarities = model.similarity(query_embeddings, doc_embeddings)
print(similarities)
# tensor([[0.8398, 0.2990],
#         [0.3282, 0.8095]])


async def main():
    client = AsyncGroq()

    stream = await client.chat.completions.create(
        #
        # Required parameters
        #
        messages=[
            # Set an optional system message. This sets the behavior of the
            # assistant and can be used to provide specific instructions for
            # how it should behave throughout the conversation.
            {
                "role": "system",
                "content": "you are a helpful assistant."
            },
            # Set a user message for the assistant to respond to.
            {
                "role": "user",
                "content": "Explain the importance of fast language models",
            }
        ],

        # The language model which will generate the completion.
        model="llama-3.3-70b-versatile",

        #
        # Optional parameters
        #

        # Controls randomness: lowering results in less random completions.
        # As the temperature approaches zero, the model will become
        # deterministic and repetitive.
        temperature=0.5,

        # The maximum number of tokens to generate. Requests can use up to
        # 2048 tokens shared between prompt and completion.
        max_completion_tokens=1024,

        # Controls diversity via nucleus sampling: 0.5 means half of all
        # likelihood-weighted options are considered.
        top_p=1,

        # A stop sequence is a predefined or user-specified text string that
        # signals an AI to stop generating content, ensuring its responses
        # remain focused and concise. Examples include punctuation marks and
        # markers like "[end]".
        stop=None,

        # If set, partial message deltas will be sent.
        stream=True,
    )

    # Print the incremental deltas returned by the LLM.
    async for chunk in stream:
        print(chunk.choices[0].delta.content, end="")

asyncio.run(main())