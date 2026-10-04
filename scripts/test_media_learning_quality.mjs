import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {replaySegment,segmentPlaybackDelayMs,connectMediaPlayer,disconnectMediaPlayer} from '../static/orena/capabilities/media-player.js';
import {transcriptTokens} from '../static/orena/capabilities/transcript-tokens.js';
assert.equal(segmentPlaybackDelayMs(1000,2000,1),1090);
assert.equal(segmentPlaybackDelayMs(1000,2000,1.25),890);
assert.equal(segmentPlaybackDelayMs(1000,1000,1),null);
assert.deepEqual(transcriptTokens("Hello, I’m learning English.").filter(x=>x.word).map(x=>x.text),['Hello','I’m','learning','English']);
assert.deepEqual(transcriptTokens('大家好，我是刘芬 AI').filter(x=>x.word).map(x=>x.text),['大','家','好','我','是','刘','芬','AI']);
const commands=[];
const frame={src:'https://www.youtube-nocookie.com/embed/abcdefghijk?enablejsapi=1',contentWindow:{postMessage(message,origin){commands.push({payload:JSON.parse(message),origin});}}};
const root={querySelector(selector){return selector==='#orenaMedia'?frame:null;}};
const playback={provider:'youtube',kind:'embed',url:'https://www.youtube-nocookie.com/embed/abcdefghijk'};
assert.equal(replaySegment(root,playback,1000,1010,1),true);
await new Promise(resolve=>setTimeout(resolve,130));
assert.deepEqual(commands.map(x=>x.payload.func),['seekTo','playVideo','pauseVideo']);
// YouTube seekTo can start playback: admission must leave the selected line paused.
globalThis.Element=class {};
globalThis.HTMLIFrameElement=class extends Element {};
globalThis.CustomEvent=class {constructor(type,options){this.type=type;this.detail=options.detail;}};
const youtubeFrame=new HTMLIFrameElement();
Object.assign(youtubeFrame,{isConnected:true,dataset:{excerptStartMs:'5000',excerptEndMs:'20000'}});
let callbacks,position=0,state=2;
globalThis.YT={Player:class {
  constructor(frame,options){callbacks=options.events;}
  seekTo(value){position=value;state=1;}
  pauseVideo(){state=2;}
  getCurrentTime(){return position;}
  getPlayerState(){return state;}
  getDuration(){return 100;}
  destroy(){}
}};
const youtubeRoot=new Element();
Object.assign(youtubeRoot,{dataset:{},querySelector:()=>youtubeFrame,dispatchEvent(){}});
assert.equal(connectMediaPlayer(youtubeRoot,playback),true);
await Promise.resolve();
callbacks.onReady();
try {
  assert.equal(position,5);
  assert.equal(state,2,'opening a selected segment does not autoplay or drift to another line');
} finally {disconnectMediaPlayer(youtubeRoot);}
console.log('Media playback and transcript tokens: PASS');
