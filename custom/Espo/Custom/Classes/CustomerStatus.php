<?php

namespace Espo\Custom\Classes;

use Espo\ORM\EntityManager;

/**
 * Works out who is a customer. A Contact with no Project, Interview or BGC Check is a
 * Prospect, with one it is a Customer, with two or more a Repeat customer. An Account is
 * a Customer when any of its Contacts is one, or when a Project is booked on it directly.
 */
class CustomerStatus
{
    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function refreshContact(?string $contactId): void
    {
        if (!$contactId) {
            return;
        }

        $contact = $this->entityManager->getEntityById('Contact', $contactId);

        if (!$contact) {
            return;
        }

        $count = $this->entityManager->getRDBRepository('CProject')
                ->where(['consultantId' => $contactId])->count()
            + $this->entityManager->getRDBRepository('CInterviewSession')
                ->where(['contactId' => $contactId, 'status!=' => 'Cancelled'])->count()
            + $this->entityManager->getRDBRepository('CBgcCheck')
                ->where(['contactId' => $contactId])->count();

        $status = $count === 0 ? 'Prospect' : ($count === 1 ? 'Customer' : 'Repeat customer');

        if ($contact->get('customerStatus') !== $status) {
            $contact->set('customerStatus', $status);
            $this->entityManager->saveEntity($contact, ['silent' => true, 'skipHooks' => true]);
        }

        $this->refreshAccount($contact->get('accountId'));
    }

    public function refreshAccount(?string $accountId): void
    {
        if (!$accountId) {
            return;
        }

        $account = $this->entityManager->getEntityById('Account', $accountId);

        if (!$account) {
            return;
        }

        $customer = $this->entityManager->getRDBRepository('Contact')
                ->where(['accountId' => $accountId, 'customerStatus!=' => 'Prospect'])->count() > 0
            || $this->entityManager->getRDBRepository('CProject')
                ->where(['accountId' => $accountId])->count() > 0;

        $status = $customer ? 'Customer' : 'Prospect';

        if ($account->get('customerStatus') !== $status) {
            $account->set('customerStatus', $status);
            $this->entityManager->saveEntity($account, ['silent' => true, 'skipHooks' => true]);
        }
    }
}
