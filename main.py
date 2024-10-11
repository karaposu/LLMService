# here is main.py

from tqdm import tqdm

from examples.llm_service import MyLLMService
from llmservice import generation_engine
import time
import re

def merge_paragraphs(paragraphs, output_file='output.txt'):
    # Join the list of paragraphs with two newlines as separators
    merged_text = '\n\n'.join(paragraphs)

    # Write the merged text to a .txt file
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(merged_text)

    print(f"Text has been saved to {output_file}")



def read_paragraphs(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        # First split on two or more newlines
        temp_paragraphs = re.split(r'\n\s*\n', content)
        final_paragraphs = []
        for para in temp_paragraphs:
            # Further split on indentation if necessary
            sub_paras = re.split(r'\n(?=\s)', para)
            for sub_para in sub_paras:
                clean_para = sub_para.strip()
                if clean_para:
                    final_paragraphs.append(clean_para)
        return final_paragraphs

# Example usage
file_path = 'Toplam.txt'
paragraphs = read_paragraphs(file_path)
print(len(paragraphs))

llmservice= MyLLMService()
# r=generation_engine.translate_to_russian(paragraphs[4])
# print(r)

translated_paragraphs=[]
for p in tqdm(paragraphs):

    r=llmservice.translate_to_russian(p)
    translated_paragraphs.append(r.content)
    # time.sleep()

merge_paragraphs(translated_paragraphs)

# print(paragraphs[4])
