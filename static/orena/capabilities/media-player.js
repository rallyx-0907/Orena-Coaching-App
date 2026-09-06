import {esc} from '../ui/html.js';

const YOUTUBE_EMBED_ORIGIN='https://www.youtube-nocookie.com';
const YOUTUBE_EMBED_PATH=/^\/embed\/[A-Za-z0-9_-]{11}$/;
const segmentTimers=new WeakMap();
const controllers=new WeakMap();
let youtubeApiPromise=null;

const COMMONS_MEDIA_HOSTS=['commons.wikimedia.org','upload.wikimedia.org'];
// Posters come from whichever provider publishes the media, so the poster
// allowlist is wider than the playback one: a YouTube lesson's thumbnail is on
// YouTube's image CDN. listening_catalog.py is the boundary that checks poster
// host against the source's own provider; this is defence in depth against an
// arbitrary origin, not a second provenance decision.
const POSTER_HOSTS=[...COMMONS_MEDIA_HOSTS,'thumb.wikimedia.org','i.ytimg.com','img.youtube.com'];

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

function clearSegmentTimer(root){
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
    if(Number.isFinite(controller.endMs)&&currentTime*1000>=controller.endMs&&state===1){
      controller.player.pauseVideo?.();
      controller.player.seekTo?.(controller.startMs/1000,true);
      currentTime=controller.startMs/1000;
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
  };
  controllers.set(root,controller);
  root.dataset.mediaClock='connecting';

  if(adapter.kind==='audio'||adapter.kind==='video'){
    controller.player={
      getCurrentTime:()=>frame.currentTime,
      getDuration:()=>frame.duration,
      getPlayerState:()=>frame.paused?2:1,
      seekTo:value=>{frame.currentTime=Math.max(0,Number(value)||0);},
      playVideo:()=>frame.play().catch(()=>{}),
      pauseVideo:()=>frame.pause(),
      isMuted:()=>frame.muted,
      mute:()=>{frame.muted=true;},
      unMute:()=>{frame.muted=false;},
      setPlaybackRate:value=>{frame.playbackRate=Number(value)||1;},
      destroy:()=>{},
    };
    const ready=()=>{
      if(controller.startMs>0&&Math.abs(frame.currentTime-controller.startMs/1000)>.1)frame.currentTime=controller.startMs/1000;
      root.dataset.mediaClock='ready';startClock(root,controller);
    };
    frame.addEventListener('loadedmetadata',ready,{once:true});
    frame.addEventListener('play',()=>emitClock(root,controller));
    frame.addEventListener('pause',()=>emitClock(root,controller));
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
          root.dataset.mediaClock='ready';
          startClock(root,controller);
        },
        onStateChange:()=>{
          if(controllers.get(root)!==controller)return;
          emitClock(root,controller);
        },
        onError:()=>{
          if(controllers.get(root)!==controller)return;
          root.dataset.mediaClock='error';
        },
      },
    });
  }).catch(()=>{
    if(controllers.get(root)===controller)root.dataset.mediaClock='error';
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
  clearSegmentTimer(root);
  const started=sendCommand(root,playback,'seekTo',[Math.max(0,startMs)/1000,true])
    &&sendCommand(root,playback,'playVideo');
  if(!started)return false;

  const delay=segmentPlaybackDelayMs(startMs,endMs,rate);
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
      if(Number.isFinite(controller.endMs)&&Number.isFinite(current)&&current*1000>=controller.endMs-100){
        controller.player.seekTo(controller.startMs/1000,true);
      }
      controller.player.playVideo();
    }
    emitClock(root,controller);
    return true;
  }catch{return false;}
}

export function setPlaybackRate(root,playback,rate){
  if(![.75,1,1.25].includes(rate))return false;
  return sendCommand(root,playback,'setPlaybackRate',[rate]);
}
