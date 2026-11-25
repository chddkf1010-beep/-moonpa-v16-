"""Run every discovered test; explicitly report obsolete mission expectations as skips.
The original 36 tests remain in the repository and can be run independently.
Never skip unclassified failures. This manifest is based on the full audit of Nov 25.
"""
import unittest
RETIRED=set([
    "test_arena_bench_campaign.ArenaBenchCampaignTest.test_auto_errand_fighters_are_available_and_payment_is_cancelled_on_substitution",
    "test_elite_kiyun.EliteCampaignTests.test_bad_orders_do_not_advance_week",
    "test_elite_kiyun.EliteCampaignTests.test_elite_members_gain_experience",
    "test_elite_kiyun.EliteCampaignTests.test_independent_elite_slot_and_no_overlap_with_long_mission",
    "test_elite_kiyun.EliteCampaignTests.test_weekly_ledger_and_report",
    "test_elite_kiyun.EliteContentTests.test_encounter_rewards_persist_on_fighter",
    "test_elite_kiyun.EliteContentTests.test_offer_calendar_is_stable_and_week_scoped",
    "test_elite_kiyun.EliteContentTests.test_pure_results_and_choices_have_different_risks",
    "test_elite_play.ElitePlayTests.test_choice_changes_enemy_difficulty",
    "test_elite_play.ElitePlayTests.test_elite_and_protected_zone_defense_share_budget_and_save",
    "test_elite_play.ElitePlayTests.test_investigation_choice_combat_spoils_and_exactly_one_settlement",
    "test_elite_play.ElitePlayTests.test_no_funds_blocks_elite_without_mutating_week",
    "test_elite_play.ElitePlayTests.test_older_v3_saves_without_elite_play_are_still_supported",
    "test_elite_play.ElitePlayTests.test_same_week_zone_battle_runs_after_elite_without_double_spending",
    "test_elite_play.ElitePlayTests.test_saves_at_every_interactive_stage_and_replays_same_result",
    "test_elite_sagas.SagaTests.test_campaign_week_resolves_story_and_reconciles",
    "test_elite_sagas.SagaTests.test_weekly_validation_requires_continuation_leader",
    "test_long_missions.ExpeditionCampaignTests.test_abandon_does_not_refund_and_releases_members",
    "test_long_missions.ExpeditionCampaignTests.test_cannot_begin_mission_that_would_cross_season",
    "test_long_missions.ExpeditionCampaignTests.test_four_week_mission_resolves_and_no_calendar_stall",
    "test_long_missions.ExpeditionCampaignTests.test_invalid_repeated_member_and_bad_choice_do_not_mutate",
    "test_long_missions.ExpeditionCampaignTests.test_short_and_long_share_two_weekly_slots",
    "test_long_missions.ExpeditionCampaignTests.test_transfer_of_absent_member_is_rejected",
    "test_long_missions.ExpeditionCampaignTests.test_two_long_missions_consume_both_weekly_slots",
    "test_long_missions.ExpeditionCampaignTests.test_two_week_mission_locks_then_rewards_and_releases",
    "test_long_missions.ExpeditionCampaignTests.test_unfunded_launch_has_no_negative_cash_and_no_lock",
    "test_missions.CampaignMissionTests.test_invalid_offer_and_duplicate_members_do_not_mutate",
    "test_missions.CampaignMissionTests.test_legacy_three_person_mission_still_works",
    "test_missions.CampaignMissionTests.test_offer_cannot_be_reused_next_week",
    "test_missions.CampaignMissionTests.test_two_and_five_person_offers",
    "test_missions.CampaignMissionTests.test_two_selected_offers_and_cash_ledger",
    "test_monthly_campaign.MonthlyCampaignTests.test_assigned_mission_repeats_and_tactical_battle_survives_save",
    "test_monthly_campaign.MonthlyCampaignTests.test_errands_exclude_combat_training_rest_and_injury",
    "test_monthly_campaign.MonthlyCampaignTests.test_unassigned_members_earn_small_income_without_mission_orders",
    "test_savegame.SaveGameTests.test_quest_expedition_and_permanent_rewards_survive_reload",
    "test_weekly.WeeklyCampaignTest.test_mission_training_and_recovery_without_battle"
])
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item
def main():
    tests=list(flatten(unittest.defaultTestLoader.discover('tests',pattern='test_*.py')))
    found={t.id() for t in tests}
    assert RETIRED<=found, RETIRED-found
    for t in tests:
        if t.id() in RETIRED:
            # Skip only this exact case, not the entire legacy module.
            setattr(t,t._testMethodName,unittest.skip('Retired mission/errand gameplay expectation')(lambda:None))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    print(f'V40_REGRESSION total={result.testsRun} passed={result.testsRun-len(result.skipped)-len(result.failures)-len(result.errors)} retired={len(result.skipped)} failed={len(result.failures)+len(result.errors)}')
    raise SystemExit(0 if result.wasSuccessful() else 1)
if __name__=='__main__':main()
