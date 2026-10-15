<?php

namespace Espo\Custom\Classes;

use Espo\ORM\EntityManager;

/**
 * Project margin, in INR.
 *  - Margin per hour: customer rate minus freelancer rate, for hourly freelancers only.
 *  - Margin: held timesheet hours times the customer rate, minus the Delivery Resource
 *    payouts recorded on the Project. It grows as timesheets are held and falls as
 *    payouts are recorded.
 */
class ProjectMargin
{
    public function __construct(
        private EntityManager $entityManager,
        private Margin $margin
    ) {}

    public function refresh(?string $projectId): void
    {
        if (!$projectId) {
            return;
        }

        $project = $this->entityManager->getEntityById('CProject', $projectId);

        if (!$project) {
            return;
        }

        $customerRate = $this->margin->toInr(
            $project->get('customerRate'),
            $project->get('customerRateCurrency')
        );
        $freelancerRate = $this->margin->toInr(
            $project->get('freelancerRate'),
            $project->get('freelancerRateCurrency')
        );

        $perHour = null;

        if ($customerRate !== null && $freelancerRate !== null && $project->get('freelancerPayType') === 'Hourly') {
            $perHour = round($customerRate - $freelancerRate, 2);
        }

        $total = null;

        if ($customerRate !== null) {
            $hours = 0.0;

            $timesheets = $this->entityManager->getRDBRepository('CTimesheet')
                ->where(['projectId' => $projectId, 'status' => 'Held'])
                ->find();

            foreach ($timesheets as $timesheet) {
                $hours += (float) $timesheet->get('hours');
            }

            $paid = 0.0;

            $payouts = $this->entityManager->getRDBRepository('CPayout')
                ->where(['projectId' => $projectId, 'payeeType' => 'Delivery Resource'])
                ->find();

            foreach ($payouts as $payout) {
                $paid += $this->margin->toInr($payout->get('amount'), $payout->get('amountCurrency')) ?? 0.0;
            }

            $total = round($hours * $customerRate - $paid, 2);
        }

        if (
            $project->get('marginPerHour') === $perHour &&
            $project->get('margin') === $total &&
            $project->get('marginCurrency') === 'INR'
        ) {
            return;
        }

        $project->set([
            'marginPerHour' => $perHour,
            'marginPerHourCurrency' => 'INR',
            'margin' => $total,
            'marginCurrency' => 'INR',
        ]);
        $this->entityManager->saveEntity($project, ['silent' => true, 'skipHooks' => true]);
    }
}
