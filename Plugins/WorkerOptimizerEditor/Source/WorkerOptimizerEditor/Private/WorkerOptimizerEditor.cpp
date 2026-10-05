#include "Modules/ModuleManager.h"
#include "UObject/Class.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogWorkerOptimizerAuthoring, Log, All);

class FWorkerOptimizerEditorModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        FModuleManager::LoadModuleChecked<IModuleInterface>(TEXT("Suzie"));
        UClass* SelectTool = FindObject<UClass>(nullptr, TEXT("/Script/ProjectArco.SelectTool"));
        UClass* ArcoView = FindObject<UClass>(nullptr, TEXT("/Script/ProjectArco.ArcoView"));
        UScriptStruct* HudAction = FindObject<UScriptStruct>(nullptr, TEXT("/Script/ProjectArco.HudAction"));
        UFunction* Receiver = SelectTool ? SelectTool->FindFunctionByName(TEXT("ReceiveHudAction")) : nullptr;
        FStructProperty* Action = Receiver ? FindFProperty<FStructProperty>(Receiver, TEXT("HudAction")) : nullptr;
        FObjectProperty* View = SelectTool ? FindFProperty<FObjectProperty>(SelectTool, TEXT("m_activeDetailWidget")) : nullptr;
        FObjectProperty* Context = ArcoView ? FindFProperty<FObjectProperty>(ArcoView, TEXT("Context")) : nullptr;
        if (!Receiver || Receiver->GetOuter() != SelectTool || Receiver->NumParms != 1 ||
            !HudAction || !Action || Action->Struct != HudAction ||
            !Action->HasAllPropertyFlags(CPF_Parm) || Action->HasAnyPropertyFlags(CPF_OutParm | CPF_ReturnParm) ||
            !View || !ArcoView || View->PropertyClass != ArcoView || !Context ||
            Context->PropertyClass->GetPathName() != TEXT("/Script/Engine.Actor"))
        {
            UE_LOG(LogWorkerOptimizerAuthoring, Error,
                TEXT("Native action contract changed; WorkerOptimizer authoring access was NOT enabled."));
            return;
        }

        // Only the editor's Suzie stubs change. Compiled graphs reference the
        // original game UFunction/property, never a function in this module.
        Receiver->FunctionFlags &= ~(FUNC_Private | FUNC_Protected);
        Receiver->FunctionFlags |= FUNC_Public | FUNC_BlueprintCallable;
        Receiver->SetMetaData(TEXT("Category"), TEXT("WorkerOptimizer Native Bridge"));
        View->SetPropertyFlags(CPF_BlueprintVisible);
        View->ClearPropertyFlags(CPF_BlueprintReadOnly);
        Context->SetPropertyFlags(CPF_BlueprintVisible);
        Context->ClearPropertyFlags(CPF_BlueprintReadOnly);
        UE_LOG(LogWorkerOptimizerAuthoring, Display, TEXT("WO_AUTHORING_READY: native action signature validated."));
    }
};

IMPLEMENT_MODULE(FWorkerOptimizerEditorModule, WorkerOptimizerEditor)
