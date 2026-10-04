/* Playback of the admitted source, shared with Listening's adapter. No source
   acquisition, extraction, synthesis or provider preparation belongs here. */
import {mediaPlayer, connectMediaPlayer, disconnectMediaPlayer, replaySegment,
  holdSegment, stopSegmentPlayback, setPlaybackRate} from '../capabilities/media-player.js';

export function originalSegmentPlayer(source, {documentImpl=globalThis.document}={}) {
  if (!source.hasModelAudio || !source.playback) return null;
  const root=documentImpl.createElement('div');
  const playback=source.playback;
  root.className='o-original-segment-player';
  root.hidden=playback.kind!=='embed';
  root.innerHTML=mediaPlayer(playback,source.title,{startMs:source.line.startMs,endMs:source.line.endMs,controls:false});
  let connected=false, finish=null, pending=null, playingRange=null;
  const stop=()=>{
    pending=null;
    playingRange=null;
    stopSegmentPlayback(root,playback);
    finish?.();finish=null;
  };
  function begin() {
    if (!pending || root.dataset.mediaClock!=='ready') return;
    const {from,to,speed}=pending;
    pending=null;
    holdSegment(root,from,to);
    setPlaybackRate(root,playback,speed);
    replaySegment(root,playback,from,to,speed);
  }
  root.addEventListener('orena:media-state',event=>{
    if(event.detail.state==='ready') begin();
    else if(['error','blocked'].includes(event.detail.state)) stop();
  });
  root.addEventListener('orena:media-time',event=>{
    const {time_ms:time,player_state:state}=event.detail;
    if (playingRange && state===1 && time>=playingRange.start-150 && time<playingRange.end) playingRange.started=true;
    // seekTo is asynchronous: the first clock may still be the prior paused
    // endpoint. Only a range that actually started can complete this playback.
    if(finish && playingRange?.started && time >= playingRange.end-150 && state!==1) {
      finish();finish=null;
      playingRange=null;
    }
  });
  return {
    root,
    park(host) {
      if (root.isConnected && host.moveBefore) host.moveBefore(root,null);
      else host.append(root);
    },
    attach(host) {
      if (!host) return;
      if (root.isConnected && host.moveBefore) host.moveBefore(root,null);
      else host.append(root);
      if (!connected) {connected=connectMediaPlayer(root,playback);}
    },
    play({from=0,to=(source.line.endMs-source.line.startMs)/1000,speed=1}={}) {
      stop();
      return new Promise(resolve=>{
        finish=resolve;
        const start=source.line.startMs+from*1000;
        const end=Math.min(source.line.endMs,source.line.startMs+to*1000);
        playingRange={start,end,started:false};
        root.dataset.segmentEndMs=String(end);
        pending={from:start,to:end,speed};
        begin();
      });
    },
    stop,
    dispose(){stop();disconnectMediaPlayer(root);root.remove();},
  };
}
