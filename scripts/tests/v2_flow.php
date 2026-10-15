<?php
// Benchteq spec v2 flow test. Creates fake records, so run it on STAGING only, never production.
// Usage: php scripts/tests/v2_flow.php /var/www/html   (path of the EspoCRM install)
// Runs spec section 10 style checks against the installed test instance.
chdir($argv[1]);
require_once 'bootstrap.php';

use Espo\Core\Application;
use Espo\ORM\EntityManager;

$app = new Application();
$app->setupSystemUser();
$em = $app->getContainer()->getByClass(EntityManager::class);

$fail = 0;
function check(string $label, $actual, $expected): void {
    global $fail;
    $ok = (is_float($actual) || is_float($expected)) ? abs((float)$actual - (float)$expected) < 0.001 : $actual === $expected;
    echo ($ok ? 'PASS' : 'FAIL') . "  $label  (got " . var_export($actual, true) . ($ok ? '' : ', expected ' . var_export($expected, true)) . ")\n";
    if (!$ok) $fail++;
}

$contact = $em->createEntity('Contact', ['firstName' => 'Ravi', 'lastName' => 'Kumar']);
$f1 = $em->createEntity('CDeliveryResource', ['name' => 'Passed Trainer', 'roleType' => 'Trainer', 'screeningResult' => 'Passed', 'technologies' => ['Java']]);
$f2 = $em->createEntity('CDeliveryResource', ['name' => 'Pending Trainer', 'roleType' => 'Trainer']);
check('freelancer default screening', $f2->get('screeningResult'), 'Pending');

$project = $em->createEntity('CProject', [
    'technology' => 'Java', 'consultantId' => $contact->getId(), 'freelancerId' => $f1->getId(),
    'freelancerPayType' => 'Hourly', 'freelancerRate' => 500, 'customerRate' => 900,
]);
check('project name formula', $project->get('name'), 'Java - Ravi Kumar');

$block = $em->createEntity('CPaymentBlock', ['projectId' => $project->getId(), 'totalHrs' => 10, 'amount' => 9000, 'startDate' => '2026-10-15']);
check('block name formula', $block->get('name'), 'Java - Ravi Kumar - 15 Oct 2026');
check('block remaining initial', $block->get('remainingHrs'), 10.0);

$mk = function (string $start, string $end) use ($em, $block) {
    return $em->createEntity('CTimesheet', ['paymentBlockId' => $block->getId(), 'dateStart' => $start, 'dateEnd' => $end, 'status' => 'Planned']);
};
$t1 = $mk('2026-10-15 15:30:00', '2026-10-15 16:30:00');
$t2 = $mk('2026-10-16 15:30:00', '2026-10-16 16:30:00');
$t3 = $mk('2026-10-17 15:30:00', '2026-10-17 16:30:00');
check('timesheet hours', $t1->get('hours'), 1.0);
check('timesheet name', $t1->get('name'), 'Support - 15 Oct');
check('timesheet freelancer default from project', $t1->get('freelancerId'), $f1->getId());

$reload = fn() => $em->getEntityById('CPaymentBlock', $block->getId());
check('planned does not count', $reload()->get('connectedHrs'), 0.0);

$t1->set('status', 'Held'); $em->saveEntity($t1);
$t2->set('status', 'Held'); $em->saveEntity($t2);
check('two held: connected', $reload()->get('connectedHrs'), 2.0);
check('two held: remaining', $reload()->get('remainingHrs'), 8.0);

$t2->set('status', 'Planned'); $em->saveEntity($t2);
check('held->planned: connected', $reload()->get('connectedHrs'), 1.0);
check('held->planned: remaining', $reload()->get('remainingHrs'), 9.0);

$em->removeEntity($t1);
check('delete held: connected', $reload()->get('connectedHrs'), 0.0);

$t3->set('status', 'No-Show'); $em->saveEntity($t3);
check('no-show counts', $reload()->get('connectedHrs'), 1.0);
$t3->set('status', 'Cancelled'); $em->saveEntity($t3);
check('cancelled does not count', $reload()->get('connectedHrs'), 0.0);

// edit duration of a held timesheet
$t2->set('status', 'Held'); $em->saveEntity($t2);
$t2->set('dateEnd', '2026-10-16 17:00:00'); $em->saveEntity($t2);
check('duration edit: hours', $em->getEntityById('CTimesheet', $t2->getId())->get('hours'), 1.5);
check('duration edit: connected', $reload()->get('connectedHrs'), 1.5);

// move timesheet to another block
$block2 = $em->createEntity('CPaymentBlock', ['projectId' => $project->getId(), 'totalHrs' => 5]);
$t2->set('paymentBlockId', $block2->getId()); $em->saveEntity($t2);
check('moved: old block', $reload()->get('connectedHrs'), 0.0);
check('moved: new block', $em->getEntityById('CPaymentBlock', $block2->getId())->get('remainingHrs'), 3.5);

// substitute freelancer
$t4 = $em->createEntity('CTimesheet', ['paymentBlockId' => $block->getId(), 'dateStart' => '2026-10-20 10:00:00', 'dateEnd' => '2026-10-20 11:00:00', 'freelancerId' => $f2->getId()]);
check('substitute freelancer kept', $t4->get('freelancerId'), $f2->getId());

// interview session
$s = $em->createEntity('CInterviewSession', ['contactId' => $contact->getId(), 'freelancerId' => $f1->getId(), 'dateStart' => '2026-10-21 10:00:00', 'dateEnd' => '2026-10-21 10:45:00', 'customerFee' => 3000, 'supporterFee' => 1500]);
check('interview name', $s->get('name'), 'Interview - Ravi Kumar - 21 Oct');
$s->set('status', 'Held');
try { $em->saveEntity($s); check('held while pending blocked', 'saved', 'blocked'); }
catch (Throwable $e) { check('held while pending blocked', get_class($e), 'Espo\\Core\\Exceptions\\BadRequest'); }
$s = $em->getEntityById('CInterviewSession', $s->getId());
$s->set(['paymentStatus' => 'Paid', 'status' => 'Held', 'feedback' => 'Good']); $em->saveEntity($s);
check('held after paid ok', $em->getEntityById('CInterviewSession', $s->getId())->get('status'), 'Held');
check('interview paidDate auto', (bool) $em->getEntityById('CInterviewSession', $s->getId())->get('paidDate'), true);

// BGC lead
$ref = $em->createEntity('CReferrer', ['name' => 'Anil Referrer', 'referralFee' => 2000]);
$prov = $em->createEntity('CProvider', ['name' => 'BGC Prov']);
$lead = $em->createEntity('Lead', ['lastName' => 'Bgc', 'serviceType' => 'BGC', 'bgcType' => 'US', 'referrerId' => $ref->getId(), 'bgcProviderId' => $prov->getId()]);
check('bgc US fee', (float) $lead->get('bgcFee'), 55000.0);
$lead->set('bgcType', 'India'); $em->saveEntity($lead);
check('bgc India fee', (float) $lead->get('bgcFee'), 18000.0);
$lead->set('bgcType', 'Both'); $em->saveEntity($lead);
check('bgc Both fee', (float) $lead->get('bgcFee'), 55000.0);
$lead2 = $em->createEntity('Lead', ['lastName' => 'Custom', 'serviceType' => 'BGC', 'bgcType' => 'India', 'bgcFee' => 12000]);
check('manual fee kept on create', (float) $lead2->get('bgcFee'), 12000.0);
check('fee currency USD', $lead->get('bgcFeeCurrency'), 'USD');

// payouts
$p = $em->createEntity('CPayout', ['payeeType' => 'Referrer', 'referrerId' => $ref->getId(), 'leadId' => $lead->getId(), 'payoutType' => 'Referral Fee', 'amount' => 2000]);
check('payout name auto', (bool) $p->get('name'), true);
check('referralPaid false while due', (bool) $em->getEntityById('Lead', $lead->getId())->get('referralPaid'), false);
$p->set('status', 'Paid'); $em->saveEntity($p);
check('referralPaid true after paid', (bool) $em->getEntityById('Lead', $lead->getId())->get('referralPaid'), true);
check('payout date auto', (bool) $em->getEntityById('CPayout', $p->getId())->get('payoutDate'), true);
$em->removeEntity($p);
check('referralPaid reset after payout removed', (bool) $em->getEntityById('Lead', $lead->getId())->get('referralPaid'), false);

$fp = $em->createEntity('CPayout', ['payeeType' => 'Delivery Resource', 'deliveryResourceId' => $f1->getId(), 'projectId' => $project->getId(), 'payoutType' => 'Hourly', 'amount' => 500]);
$t2->set('payoutId', $fp->getId()); $em->saveEntity($t2);
check('timesheet payout link', $em->getEntityById('CTimesheet', $t2->getId())->get('payoutId'), $fp->getId());

echo $fail ? "\n$fail FAILED\n" : "\nALL PASSED\n";
exit($fail ? 1 : 0);
