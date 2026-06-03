# Vehicle taxonomy mapping design note > i dont really like this. i get it though. I think we should focus more on making the design to handle the needs of the modules 2-7, and keep detail aboutn the exact mapping rules for later, once we haVE CODE to impolement it, we can write the rules post hoc. But some thing we provably can do now are: reocrd the leap branch sturcutre for trnaspor model. r3eocrd the m,easures we need for what branches and what other measures are needed for leap such as profiles (lficelcyel and vintage prifiles), but also factors used only in module 2-7. we can also rerord dewtails about the branches and the deicisons about waht cvateogyires were chosen to help with input data processing and decisions. I think once we have a loto fo this stuff we can better proceed with other decisions around m,apping ruels, verification and validation etc. 

## Purpose

Define a robust, auditable mapping from Module 1 / LEAP branch taxonomy to model vehicle categories.

Current concern: LPV and size-labelled branches do not always align 1:1 with `passenger_car` vs `suv_light_truck` categories.

## Proposed approach (design-first)

1. **Single mapping table source**
   - Add a CSV source table (future) with columns such as:
     - `source_branch_pattern`
     - `transport_type`
     - `vehicle_type`
     - `size`
     - `priority`
     - `active`
     - `mapping_note`
2. **Deterministic matching order**
   - Exact pattern match first.
   - Then wildcard/path-prefix match.
   - Then explicit fallback rows.
3. **Validation rules**
   - Every required model vehicle type must be reachable.
   - No branch should map to multiple active outputs at same priority.
   - Report all unmatched branches as validation errors.
4. **Cross-repo alignment**
   - Reconcile naming and branch semantics with `leap_road_model` before implementation.

## PHEV liquid-fuel split policy

For Module 6, the PHEV liquid-fuel split should follow the same broad liquid-fuel structure used by the transport sector:

- infer the gasoline/diesel mixing rate from the transport-sector quantities already available;
- apply that same inferred gasoline/diesel blend to PHEV liquid demand within the original vehicle type;
- treat biodiesel and biogasoline as part of the inferred liquid blend;
- ignore LPG and CNG for the PHEV liquid split in the first version.

This policy keeps PHEVs consistent with the rest of the drive taxonomy while avoiding a separate PHEV-specific LPG/CNG allocation rule.

## Preview: how this works and looks

To make the design concrete, a small preview script is included:

- `back-end/scripts/preview_vehicle_taxonomy_mapping.py`

The preview demonstrates the deterministic order described above:

1. exact match
2. wildcard/path-prefix match
3. explicit fallback

It prints a compact table showing, per source branch:

- matched mode (`exact` / `wildcard` / `fallback`)
- chosen model vehicle type
- winning pattern rule

Example output shape:

| source_branch_path | mode | vehicle_type | pattern |
| --- | --- | --- | --- |
| Demand\\Passenger road\\LPVs\\ICE small\\Motor gasoline | exact | passenger_car | Demand\\Passenger road\\LPVs\\ICE small\\Motor gasoline |
| Demand\\Passenger road\\LPVs\\ICE medium\\Motor gasoline | wildcard | passenger_car | Demand\\Passenger road\\LPVs\\ICE *\\Motor gasoline |
| Demand\\Passenger road\\Buses\\ICE\\Motor gasoline | fallback | passenger_car | * |

The script also reports a summary count (`Total`, `Matched`, `Unmatched`) so validation behavior is visible.

## Scope boundaries

- This note is design-only for now.
- No code changes to taxonomy mapping are made in this step.
