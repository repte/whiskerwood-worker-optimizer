#include "WorkerOptimizerUIAuthoring.h"

#include "Animation/WidgetAnimation.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "MovieScene.h"
#include "WidgetBlueprint.h"

UWidgetAnimation* UWorkerOptimizerUIAuthoring::CreatePulseAnimation(UBlueprint* WidgetBP, FName Name, float Seconds)
{
    UWidgetBlueprint* Blueprint = Cast<UWidgetBlueprint>(WidgetBP);
    if (!Blueprint || Name.IsNone() || !FMath::IsFinite(Seconds) || Seconds <= 0.f || Seconds > 60.f)
    {
        return nullptr;
    }

    UWidgetAnimation* Animation = nullptr;
    for (UWidgetAnimation* Candidate : Blueprint->Animations)
    {
        if (Candidate && Candidate->GetFName() == Name)
        {
            Animation = Candidate;
            break;
        }
    }

    // Regeneration may update a pulse range, but must not replace authored tracks.
    if (Animation && (!Animation->MovieScene || !Animation->GetBindings().IsEmpty()
        || !Animation->MovieScene->GetTracks().IsEmpty()
        || !static_cast<const UMovieScene*>(Animation->MovieScene.Get())->GetBindings().IsEmpty()))
    {
        return nullptr;
    }
    if (!Animation && (FindObjectFast<UObject>(Blueprint, Name)
        || Blueprint->NewVariables.ContainsByPredicate([Name](const FBPVariableDescription& Variable) { return Variable.VarName == Name; })))
    {
        return nullptr;
    }

    Blueprint->Modify();
    if (!Animation)
    {
        Animation = NewObject<UWidgetAnimation>(Blueprint, Name, RF_Transactional);
        Animation->SetDisplayLabel(Name.ToString());
        Animation->MovieScene = NewObject<UMovieScene>(Animation, Name, RF_Transactional);
        Blueprint->Animations.Add(Animation);
    }
    Animation->Modify();
    UMovieScene* MovieScene = Animation->MovieScene;
    MovieScene->Modify();

    // Millisecond resolution makes the 10/150/250 ms UI pulses exact asset ranges.
    MovieScene->SetTickResolutionDirectly(FFrameRate(1000, 1));
    MovieScene->SetDisplayRate(FFrameRate(60, 1));
    MovieScene->SetPlaybackRange(FFrameNumber(0), FMath::Max(1, FMath::RoundToInt(Seconds * 1000.f)));
    MovieScene->GetEditorData().WorkStart = 0.f;
    MovieScene->GetEditorData().WorkEnd = Seconds;

    // The widget compiler generates and initializes the read-only animation property.
    if (!Blueprint->WidgetVariableNameToGuidMap.Contains(Name))
    {
        Blueprint->OnVariableAdded(Name);
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return Animation;
}
