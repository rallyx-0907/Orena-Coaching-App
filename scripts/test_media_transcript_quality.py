from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from writing_coach.media_transcript_quality import CaptionUnit,clean_caption_text,clean_caption_units
import writing_coach.media_transcript_quality as transcript_quality
repair_english_caption_text=getattr(transcript_quality,"repair_english_caption_text",None)
assert callable(repair_english_caption_text), "the bounded English caption repair is missing"
assert clean_caption_text("[Music]")==""
assert repair_english_caption_text(">>  hello   world [music]")=="hello world"
assert repair_english_caption_text("[Music]  >> GOOD MORNING")=="GOOD MORNING"
assert repair_english_caption_text("I like 2 cats")=="I like 2 cats"
assert clean_caption_text("♪  Hello   world  ♪")=="Hello world"
assert clean_caption_text("（音乐）")==""
zh=clean_caption_units((CaptionUnit("大家好，欢迎来到每天中文",0,3,0),CaptionUnit("Hello everyone and welcome to Everyday Chinese",0,3,1),CaptionUnit("I am Liu Fen.",3,2,2),CaptionUnit("我是刘芬",3,2,3),CaptionUnit("[Music]",5,1,4),CaptionUnit("大家好，我是陈杰",5,2,5),CaptionUnit("Hello, my name is Chen Jie.",5,2,6)),source_language="zh")
assert [x.text for x in zh]==["大家好，欢迎来到每天中文","我是刘芬","大家好，我是陈杰"]
en=clean_caption_units((CaptionUnit("大家好，欢迎来到每天中文",0,3,0),CaptionUnit("Hello everyone and welcome to Everyday Chinese",0,3,1),CaptionUnit("I am Liu Fen.",3,2,2),CaptionUnit("我是刘芬",3,2,3)),source_language="en")
assert [x.text for x in en]==["Hello everyone and welcome to Everyday Chinese","I am Liu Fen."]
assert [x.text for x in clean_caption_units((CaptionUnit("OpenAI",8,1,0),),source_language="zh")]==["OpenAI"]
dupes=clean_caption_units((CaptionUnit("Repeated caption",3,0.5,0),CaptionUnit("Repeated caption",3,0.5,1)),source_language="en")
assert [x.text for x in dupes]==["Repeated caption","Repeated caption"]
print("Media transcript quality cleanup: PASS")
