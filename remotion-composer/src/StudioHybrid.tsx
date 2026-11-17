// AGPL-3.0. Structured, non executable creative data from the hybrid directors.
import React from 'react';
import {AbsoluteFill, Composition, Img, OffthreadVideo, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveAsset} from './lib/resolveAsset';
import {loadSpaceGrotesk} from './lib/localFonts';

const {fontFamily}=loadSpaceGrotesk(['400','700']);
type Beat={id:string;role:string;seconds:number;copy:string;purpose:string;source:string;mime:string;motion:string};
type Metadata={beats:Beat[];brand:string;website:string;color:string;width:number;height:number;duration_seconds:number};
export type StudioHybridProps={metadata:Metadata};
const BeatView:React.FC<{beat:Beat;index:number;metadata:Metadata}>=({beat,index,metadata:m})=>{
  const frame=useCurrentFrame();const {fps,width,height}=useVideoConfig();
  const duration=Math.round(beat.seconds*fps),portrait=height>width;
  const enter=spring({frame,fps,config:{damping:24,stiffness:150}});
  const outro=interpolate(frame,[duration-7,duration],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const action=beat.role==='action',hook=beat.role==='hook';
  const split=!portrait&&!action&&!hook&&index%2===1;
  const scale=interpolate(frame,[0,duration],[1.08,1.17]);
  const shift=interpolate(frame,[0,duration],[index%2?-2:2,index%2?2:-2]);
  const words=beat.copy.split(/\s+/).filter(Boolean);
  return <AbsoluteFill style={{background:'#10191e',fontFamily,color:'#fff',overflow:'hidden'}}>
    {beat.source&&<AbsoluteFill style={{left:split?'35%':0,transform:beat.mime.startsWith('video/')?'none':`translateX(${shift}%) scale(${scale})`}}>
      {beat.mime.startsWith('video/')?<OffthreadVideo src={resolveAsset(beat.source)} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<Img src={resolveAsset(beat.source)} style={{width:'100%',height:'100%',objectFit:'cover'}}/>}
    </AbsoluteFill>}
    <AbsoluteFill style={{background:split?'linear-gradient(90deg,#10191e 30%,rgba(16,25,30,.75) 52%,transparent 80%)':'linear-gradient(0deg,rgba(9,16,24,.88),rgba(9,16,24,.18) 75%)'}}/>
    <div style={{position:'absolute',left:width*.055,top:height*.055,fontSize:Math.round(width*(portrait?.045:.024)),fontWeight:700,letterSpacing:1}}>{m.brand}</div>
    <div style={{position:'absolute',left:width*.055,right:width*(split?.43:.065),bottom:height*(action?.25:.16),opacity:outro,transform:`translateY(${(1-enter)*30}px)`}}>
      <div style={{width:interpolate(enter,[0,1],[0,width*.07]),height:6,background:m.color,marginBottom:height*.025}}/>
      <div style={{fontWeight:700,fontSize:Math.round(width*(portrait?.087:split?.046:.05)),lineHeight:1.12,letterSpacing:-1.5}}>
        {words.map((word,i)=><span key={i} style={{display:'inline-block',marginRight:'.22em',opacity:interpolate(frame,[3+i*2,9+i*2],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),transform:`translateY(${interpolate(frame,[3+i*2,12+i*2],[18,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`}}>{word}</span>)}
      </div>
      {action&&<div style={{marginTop:height*.04,fontSize:width*(portrait?.045:.023),color:'#e0e5ef'}}>{m.website.replace(/^https?:\/\//,'').replace(/\/$/,'')}</div>}
    </div>
    <div style={{position:'absolute',bottom:0,left:0,height:5,width:`${Math.min(100,(frame/duration)*100)}%`,background:m.color}}/>
    <AbsoluteFill style={{background:m.color,transform:`translateX(${interpolate(frame,[0,7],[0,101],{extrapolateRight:'clamp'})}%)`}}/>
  </AbsoluteFill>;
};
export const StudioHybrid:React.FC<StudioHybridProps>=({metadata})=>{let cursor=0;return <AbsoluteFill>{metadata.beats.map((beat,index)=>{const from=cursor;cursor+=Math.round(beat.seconds*30);return <Sequence key={beat.id} from={from} durationInFrames={Math.round(beat.seconds*30)}><BeatView beat={beat} index={index} metadata={metadata}/></Sequence>;})}</AbsoluteFill>;};
export const StudioHybridComposition=()=> <Composition id="StudioHybrid" component={StudioHybrid} fps={30} width={1920} height={1080} durationInFrames={450}
  defaultProps={{metadata:{beats:[],brand:'',website:'',color:'#6246ea',width:1920,height:1080,duration_seconds:15}}}
  calculateMetadata={({props})=>({width:props.metadata.width,height:props.metadata.height,durationInFrames:Math.round(props.metadata.duration_seconds*30)})}/>;
