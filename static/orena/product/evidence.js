import {evaluateListeningReconstruction,listeningReconstructionDiff} from '../capabilities/dictation-evaluator.js';
// Adapt existing server evidence contracts without a screen-oriented session.
export function dictationEvidence({asset,segment,language,previous={}}) {
  let evidence={asset_id:asset,segment_id:segment.segment_id,presentation:'prompt',revealed:Boolean(previous.revealed),checked_attempt_count:previous.checked_attempt_count||0,best_accuracy_percent:previous.best_accuracy_percent??null,best_exact:Boolean(previous.best_exact),last_answer:previous.last_answer||''};
  return {
    get value(){return {...evidence};},
    compare(answer){const result=evaluateListeningReconstruction({source_language:language,expected:segment.original_text,answer});evidence={...evidence,presentation:'checked',checked_attempt_count:Math.min(1000,evidence.checked_attempt_count+1),best_accuracy_percent:Math.max(evidence.best_accuracy_percent??0,result.accuracy_percent),best_exact:evidence.best_exact||result.exact,last_answer:answer};return {result,diff:listeningReconstructionDiff({source_language:language,expected:segment.original_text,answer})};},
    reveal(){evidence={...evidence,presentation:'revealed',revealed:true};return this.value;},
  };
}
