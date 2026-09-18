import {esc} from '../ui/html.js';

const YOUTUBE_EMBED_ORIGIN='https://www.youtube-nocookie.com';
const YOUTUBE_EMBED_PATH=/^\/embed\/[A-Za-z0-9_-]{11}$/;
const segmentTimers=new WeakMap();
// One clock tick of slack, so a pause that lands a few milliseconds past the
// end of a held line is not read as the learner having left it.
const HOLD_TOLERANCE_MS=150;
const controllers=new WeakMap();
let youtubeApiPromise=null;
function mediaState(root,state){
  root.dataset.mediaClock=state;
  root.dispatchEvent?.(new CustomEvent('orena:media-state',{detail:{state}}));
}

const COMMONS_MEDIA_HOSTS=['commons.wikimedia.org','upload.wikimedia.org'];
// Posters come from whichever provider publishes the media, so the poster
// allowlist is wider than the playback one: a YouTube lesson's thumbnail is on
// YouTube's image CDN. listening_catalog.py is the boundary that checks poster
// host against the source's own provider; this is defence in depth against an
// arbitrary origin, not a second provenance decision.
const POSTER_HOSTS=[...COMMONS_MEDIA_HOSTS,'thumb.wikimedia.org','i.ytimg.com','img.youtube.com'];

/* Media Orena stores itself - a learner's uploaded file, or the thumbnail the
   importer generated for it - is served from this application's own origin
   under an opaque, server-validated key. It is addressed as a relative path,
   which is the property that matters here: a relative path cannot point the
   page at another origin, so it needs no host allowlist, while an absolute URL
   on any other host is still refused by reviewedMediaUrl() below. The prefix
   is explicit rather than "anything under /api/" so the boundary stays
   readable: only these two routes can ever be played or attached. */
const ORENA_MEDIA_PATH=/^\/api\/media\/files\/[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/;
const ORENA_ARTWORK_PATH=/^\/api\/media\/library\/assets\/[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/;
function sameOriginMedia(value,pattern){
  const raw=String(value||'');
  return pattern.test(raw)?raw:null;
}

// One reviewed-media URL policy, matching listening_catalog.py and the native
// adapter: https, an exact allowlisted host, no credentials, no port.
function reviewedMediaUrl(value,hosts=COMMONS_MEDIA_HOSTS){
  try{
    const url=new URL(String(value||''));
    if(url.protocol!=='https:'||url.username||url.password||url.port)return null;
    return hosts.includes(url.hostname)?url.href:null;
  }catch{return null;}
}

function playbackAdapter(playback){
  if(playback?.kind==='audio'||playback?.kind==='video'){
    if(playback?.provider==='orena'){
      const href=sameOriginMedia(playback.url,ORENA_MEDIA_PATH);
      if(!href)return null;
      return {kind:playback.kind,url:href,origin:globalThis.location?.origin||'',controllable:true};
    }
    if(playback.provider!=='wikimedia-commons')return null;
    const href=reviewedMediaUrl(playback.url);
    if(!href)return null;
    return {kind:playback.kind,url:href,origin:new URL(href).origin,controllable:true};
  }
  if(playback?.kind!=='embed')return null;
  try{
    const url=new URL(playback.url);
    if(url.protocol!=='https:'||url.username||url.password||playback.provider!=='youtube')return null;
    if(url.origin!==YOUTUBE_EMBED_ORIGIN||!YOUTUBE_EMBED_PATH.test(url.pathname))return null;
    url.search='';
    url.hash='';
    url.searchParams.set('enablejsapi','1');
    const pageOrigin=globalThis.location?.origin;
    if(typeof pageOrigin==='string'&&/^https?:\/\//.test(pageOrigin)){
      url.searchParams.set('origin',pageOrigin);
    }
    return {kind:'youtube',url:url.href,origin:url.origin,controllable:true};
  }catch{return null;}
}

function ensureYouTubeIframeApi(){
  if(globalThis.YT?.Player)return Promise.resolve(globalThis.YT);
  if(youtubeApiPromise)return youtubeApiPromise;

  youtubeApiPromise=new Promise((resolve,reject)=>{
    const previousReady=globalThis.onYouTubeIframeAPIReady;
    let settled=false;
    const finish=()=>{
      if(settled||!globalThis.YT?.Player)return;
      settled=true;
      resolve(globalThis.YT);
    };

    globalThis.onYouTubeIframeAPIReady=()=>{
      try{
        if(typeof previousReady==='function')previousReady();
      }finally{
        finish();
      }
    };

    let script=document.querySelector('script[data-orena-youtube-iframe-api]');
    if(!script){
      script=document.createElement('script');
      script.src='https://www.youtube.com/iframe_api';
      script.async=true;
      script.dataset.orenaYoutubeIframeApi='true';
      document.head.appendChild(script);
    }
    script.addEventListener('load',finish,{once:true});
    script.addEventListener('error',()=>{
      if(settled)return;
      settled=true;
      reject(new Error('YouTube IFrame API failed to load.'));
    },{once:true});

    setTimeout(()=>{
      if(settled)return;
      if(globalThis.YT?.Player)finish();
      else{
        settled=true;
        reject(new Error('YouTube IFrame API timed out.'));
      }
    },10000);
  });

  return youtubeApiPromise;
}

/* What a held player owes the line it is holding, given where it is now.

   Pure, and exported, so the boundary can be checked with numbers rather than
   with a regular expression over this file. Three answers and no others:

     'pause' - the line has been heard out
     'seek'  - playback is somewhere else entirely and belongs back at the line
     null    - inside the line, or stopped, so nothing is owed

   A stopped player is never moved: a learner who paused mid-line and went to
   write it down comes back to where they paused. */
export function segmentHoldAction(hold,timeMs,playing){
  const start=Number(hold?.start_ms),end=Number(hold?.end_ms),at=Number(timeMs);
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start||!Number.isFinite(at))return null;
  if(!playing)return null;
  if(at>=end)return 'pause';
  if(at<start-HOLD_TOLERANCE_MS||at>end+HOLD_TOLERANCE_MS)return 'seek';
  return null;
}

function clearSegmentTimer(root){
  const controller=controllers.get(root);if(controller)controller.segmentEndMs=null;
  const timer=segmentTimers.get(root);
  if(timer!==undefined){
    clearTimeout(timer);
    segmentTimers.delete(root);
  }
}

function stopClock(controller){
  if(controller?.pollTimer!==null&&controller?.pollTimer!==undefined){
    clearInterval(controller.pollTimer);
    controller.pollTimer=null;
  }
}

function destroyController(root){
  const controller=controllers.get(root);
  if(!controller)return;
  stopClock(controller);
  try{controller.player?.destroy?.();}catch{}
  controllers.delete(root);
  root.dataset.mediaClock='disconnected';
}

function emitClock(root,controller){
  if(!controller?.player||!controller.frame?.isConnected){
    destroyController(root);
    return;
  }
  try{
    let currentTime=Number(controller.player.getCurrentTime?.());
    if(!Number.isFinite(currentTime))return;
    let state=Number(controller.player.getPlayerState?.());
    /* A held segment is the whole of what may be played.

       Dictation is the reason this exists: a learner writing down line 3 must
       hear line 3, and nothing after it. A one-shot "pause at this time" only
       binds playback that replaySegment() itself started, so the native
       controls, the transport's own play button, or a seek would run the
       source straight on through the next five lines. A hold binds the player
       instead of the call: whatever starts it, playback stays inside the line.

       The clock polls at 125ms, so the pause lands within one tick of the end
       rather than exactly on it; HOLD_TOLERANCE_MS keeps a seek from fighting
       that overshoot, and keeps a segment boundary that the transcript reports
       a few milliseconds early from re-seeking on its own. */
    const holding=segmentHoldAction(
      {start_ms:controller.holdStartMs,end_ms:controller.holdEndMs},
      currentTime*1000,
      state===1,
    );
    if(holding==='pause'){controller.player.pauseVideo?.();state=2;}
    else if(holding==='seek')controller.player.seekTo?.(controller.holdStartMs/1000,true);
    if(Number.isFinite(controller.segmentEndMs)&&currentTime*1000>=controller.segmentEndMs&&state===1){
      controller.player.pauseVideo?.();controller.segmentEndMs=null;state=2;
    }
    if(Number.isFinite(controller.endMs)&&currentTime*1000>=controller.endMs&&state===1){
      controller.player.pauseVideo?.();

      state=2;
    }
    root.dataset.mediaClock='ready';
    root.dispatchEvent(new CustomEvent('orena:media-time',{
      bubbles:true,
      detail:{
        time_ms:Math.max(0,Math.round(currentTime*1000)),
        // The progress bar needs a length, not just a position. Duration is
        // read from the same player object and is null until it is known,
        // which the caller must treat as "no bar yet" rather than zero.
        duration_ms:(()=>{
          const total=Number(controller.player.getDuration?.());
          return Number.isFinite(total)&&total>0?Math.round(total*1000):null;
        })(),
        player_state:Number.isFinite(state)?state:null,
      },
    }));
  }catch{}
}

function startClock(root,controller){
  stopClock(controller);
  emitClock(root,controller);
  controller.pollTimer=setInterval(()=>emitClock(root,controller),125);
}

export function connectMediaPlayer(root,playback){
  if(!(root instanceof Element))return false;
  const adapter=playbackAdapter(playback);
  const frame=root.querySelector('#orenaMedia');
  const validFrame=adapter?.kind==='audio'
    ?frame instanceof HTMLAudioElement
    :adapter?.kind==='video'
      ?frame instanceof HTMLVideoElement
      :frame instanceof HTMLIFrameElement;
  if(!adapter||!validFrame){
    destroyController(root);
    return false;
  }

  const existing=controllers.get(root);
  if(existing?.frame===frame&&existing?.player)return true;
  destroyController(root);

  const parsedStart=Number(frame.dataset.excerptStartMs);
  const parsedEnd=Number(frame.dataset.excerptEndMs);
  const controller={
    frame,
    player:null,
    pollTimer:null,
    startMs:Number.isFinite(parsedStart)&&parsedStart>=0?parsedStart:0,
    endMs:Number.isFinite(parsedEnd)&&parsedEnd>parsedStart?parsedEnd:null,
    holdStartMs:null,
    holdEndMs:null,
  };
  controllers.set(root,controller);
  mediaState(root,'connecting');

  if(adapter.kind==='audio'||adapter.kind==='video'){
    controller.player={
      getCurrentTime:()=>frame.currentTime,
      getDuration:()=>frame.duration,
      getPlayerState:()=>frame.paused?2:1,
      seekTo:value=>{frame.currentTime=Math.max(0,Number(value)||0);},
      playVideo:()=>frame.play().catch(error=>{
        if(controllers.get(root)===controller)mediaState(root,error?.name==='NotAllowedError'?'blocked':'error');
      }),
      pauseVideo:()=>frame.pause(),
      isMuted:()=>frame.muted,
      mute:()=>{frame.muted=true;},
      unMute:()=>{frame.muted=false;},
      setPlaybackRate:value=>{frame.playbackRate=Number(value)||1;},
      destroy:()=>{
        frame.removeEventListener?.('loadedmetadata',ready);
        frame.removeEventListener?.('play',clock);
        frame.removeEventListener?.('pause',clock);
        frame.removeEventListener?.('error',failed);
        frame.pause();
      },
    };
    const ready=()=>{
      if(controllers.get(root)!==controller||!frame.isConnected)return;
      if(controller.startMs>0&&Math.abs(frame.currentTime-controller.startMs/1000)>.1)frame.currentTime=controller.startMs/1000;
      mediaState(root,'ready');startClock(root,controller);
    };
    const clock=()=>{if(controllers.get(root)===controller){mediaState(root,'ready');emitClock(root,controller);}};
    const failed=()=>{if(controllers.get(root)===controller)mediaState(root,'error');};
    frame.addEventListener('loadedmetadata',ready,{once:true});
    frame.addEventListener('play',clock);
    frame.addEventListener('pause',clock);
    frame.addEventListener('error',failed);
    if(frame.readyState>=1)ready();
    return true;
  }

  ensureYouTubeIframeApi().then(YT=>{
    if(controllers.get(root)!==controller||!frame.isConnected)return;
    controller.player=new YT.Player(frame,{
      events:{
        onReady:()=>{
          if(controllers.get(root)!==controller)return;
          if(controller.startMs>0)controller.player.seekTo(controller.startMs/1000,true);
          mediaState(root,'ready');
          startClock(root,controller);
        },
        onStateChange:()=>{
          if(controllers.get(root)!==controller)return;
          emitClock(root,controller);
        },
        onError:()=>{
          if(controllers.get(root)!==controller)return;
          mediaState(root,'error');
        },
      },
    });
  }).catch(()=>{
    if(controllers.get(root)===controller)mediaState(root,'error');
  });

  return true;
}

export function disconnectMediaPlayer(root){
  if(!(root instanceof Element))return;
  clearSegmentTimer(root);
  destroyController(root);
}

function sendCommand(root,playback,func,args=[]){
  const adapter=playbackAdapter(playback);
  if(!adapter?.controllable)return false;

  const controller=controllers.get(root);
  if(controller?.player){
    try{
      const method=controller.player?.[func];
      if(typeof method==='function'){
        method.apply(controller.player,args);
        emitClock(root,controller);
        return true;
      }
    }catch{}
  }

  if(adapter.kind==='audio')return false;
  const frame=root.querySelector('#orenaMedia');
  if(!frame?.contentWindow?.postMessage)return false;
  try{
    if(new URL(frame.src).origin!==adapter.origin)return false;
  }catch{return false;}
  frame.contentWindow.postMessage(JSON.stringify({event:'command',func,args}),adapter.origin);
  return true;
}

export function playbackAvailable(playback){
  return playbackAdapter(playback)!==null;
}

// A poster only ever decorates a player; it must never become a way to point
// the page at an arbitrary host, so it is held to the same Commons origins.
export function posterUrl(poster){
  return typeof poster==='string'&&poster?(reviewedMediaUrl(poster,POSTER_HOSTS)||''):'';
}

export function mediaPlayer(playback,title,{startMs=0,endMs=null,poster=''}={}){
  const adapter=playbackAdapter(playback);
  if(!adapter)return '<div class="listening-player-unavailable" role="status">Playback is unavailable for this source.</div>';
  const safeStart=Math.max(0,Number(startMs)||0);
  const safeEnd=Number(endMs);
  const bounds=`data-excerpt-start-ms="${safeStart}" ${Number.isFinite(safeEnd)&&safeEnd>safeStart?`data-excerpt-end-ms="${safeEnd}"`:''}`;
  if(adapter.kind==='audio')return `<audio id="orenaMedia" src="${esc(adapter.url)}" aria-label="${esc(title||'Lesson audio')}" preload="metadata" ${bounds}></audio>`;
  if(adapter.kind==='video'){
    const art=posterUrl(poster);
    return `<video id="orenaMedia" src="${esc(adapter.url)}"${art?` poster="${esc(art)}"`:''} title="${esc(title||'Lesson video')}" aria-label="${esc(title||'Lesson video')}" preload="metadata" playsinline controls ${bounds}></video>`;
  }
  return `<iframe id="orenaMedia" src="${esc(adapter.url)}" title="${esc(title||'Lesson video')}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin" ${bounds}></iframe>`;
}

export function segmentPlaybackDelayMs(startMs,endMs,rate=1){
  const start=Number(startMs),end=Number(endMs),speed=Number(rate);
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start||!Number.isFinite(speed)||speed<=0)return null;
  return Math.max(80,Math.round((end-start)/speed)+90);
}

/* Bind the player to one line until it is released.

   `holdSegment` is what a task that is about a single line - Dictation, and
   any practice that follows it - uses instead of trusting every entry point to
   remember the boundary. `releaseSegment` gives the whole source back. */
export function holdSegment(root,startMs,endMs){
  const controller=controllers.get(root);
  const start=Number(startMs),end=Number(endMs);
  if(!controller||!Number.isFinite(start)||!Number.isFinite(end)||end<=start)return false;
  controller.holdStartMs=Math.max(0,start);
  controller.holdEndMs=end;
  return true;
}

export function releaseSegment(root){
  const controller=controllers.get(root);
  if(!controller)return false;
  controller.holdStartMs=null;
  controller.holdEndMs=null;
  return true;
}

export function heldSegment(root){
  const controller=controllers.get(root);
  return Number.isFinite(controller?.holdEndMs)
    ?{start_ms:controller.holdStartMs,end_ms:controller.holdEndMs}
    :null;
}

export function stopSegmentPlayback(root,playback){
  clearSegmentTimer(root);
  return sendCommand(root,playback,'pauseVideo');
}

export function seekPlayback(root,playback,timeMs){
  clearSegmentTimer(root);
  const value=Number(timeMs);
  if(!Number.isFinite(value)||value<0)return false;
  return sendCommand(root,playback,'seekTo',[value/1000,true]);
}

export function replaySegment(root,playback,startMs,endMs=null,rate=1){
  // clearSegmentTimer() drops the one-shot boundary only; a held line outlives
  // every replay inside it, which is what keeps Dictation bounded when the
  // learner presses Replay a fourth time.
  clearSegmentTimer(root);
  const started=sendCommand(root,playback,'seekTo',[Math.max(0,startMs)/1000,true])
    &&sendCommand(root,playback,'playVideo');
  if(!started)return false;

  const delay=segmentPlaybackDelayMs(startMs,endMs,rate);
  const controller=controllers.get(root);
  if(controller&&delay!==null){controller.segmentEndMs=Number(endMs);return true;}
  if(delay!==null){
    const timer=setTimeout(()=>{
      sendCommand(root,playback,'pauseVideo');
      segmentTimers.delete(root);
    },delay);
    segmentTimers.set(root,timer);
  }
  return true;
}

/* Nudge the position without leaving the segment machinery in a half state:
   any pending "pause at the end of this segment" timer is dropped first, or it
   would fire against a position the learner has already moved away from. */
export function seekBy(root,playback,deltaSeconds){
  const controller=controllers.get(root);
  const step=Number(deltaSeconds);
  if(!controller?.player||!Number.isFinite(step))return false;
  try{
    const current=Number(controller.player.getCurrentTime?.());
    if(!Number.isFinite(current))return false;
    clearSegmentTimer(root);
    return sendCommand(root,playback,'seekTo',[Math.max(0,current+step),true]);
  }catch{return false;}
}

/* Returns the new muted state, or null when the player cannot be reached, so
   the caller can label its own button from the truth rather than a guess. */
export function toggleMute(root,playback){
  const controller=controllers.get(root);
  if(!controller?.player)return null;
  try{
    const muted=Boolean(controller.player.isMuted?.());
    const ok=sendCommand(root,playback,muted?'unMute':'mute');
    return ok?!muted:null;
  }catch{return null;}
}

export function togglePlayback(root,playback){
  const controller=controllers.get(root);
  if(!controller?.player)return false;
  try{
    const state=Number(controller.player.getPlayerState?.());
    if(state===1)controller.player.pauseVideo();
    else{
      const current=Number(controller.player.getCurrentTime?.());
      // Play inside a held line always means "play this line", from wherever
      // in it the learner is - and from its start once it has been heard out.
      if(Number.isFinite(controller.holdEndMs)&&Number.isFinite(current)&&
        (current*1000>=controller.holdEndMs-HOLD_TOLERANCE_MS||current*1000<controller.holdStartMs)){
        controller.player.seekTo(controller.holdStartMs/1000,true);
      }else if(Number.isFinite(controller.endMs)&&Number.isFinite(current)&&current*1000>=controller.endMs-100){
        controller.player.seekTo(controller.startMs/1000,true);
      }
      controller.player.playVideo();
    }
    emitClock(root,controller);
    return true;
  }catch{return false;}
}

export function setPlaybackRate(root,playback,rate){
  if(![.5,.75,1,1.25,1.5,2].includes(rate))return false;
  return sendCommand(root,playback,'setPlaybackRate',[rate]);
}
