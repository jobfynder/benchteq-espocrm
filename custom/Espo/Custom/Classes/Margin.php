<?php

namespace Espo\Custom\Classes;

use Espo\Core\Currency\Converter;
use Espo\Core\Field\Currency;
use Espo\Core\InjectableFactory;
use Espo\ORM\Entity;
use Throwable;

/**
 * Margin = what the customer pays minus what we pay out, in INR. It stays empty until both
 * amounts are known. The amounts can be in
 * different currencies, so both are converted with the rates in Administration, Currency.
 */
class Margin
{
    private const CODE = 'INR';

    public function __construct(
        private InjectableFactory $injectableFactory
    ) {}

    public function apply(Entity $entity, string $incomeField, string $costField): void
    {
        $income = $this->toInr($entity->get($incomeField), $entity->get($incomeField . 'Currency'));
        $cost = $this->toInr($entity->get($costField), $entity->get($costField . 'Currency'));

        if ($income === null || $cost === null) {
            $entity->set('margin', null);
            $entity->set('marginCurrency', null);

            return;
        }

        $entity->set('margin', round($income - $cost, 2));
        $entity->set('marginCurrency', self::CODE);
    }

    public function toInr(mixed $amount, mixed $code): ?float
    {
        if ($amount === null || !$code) {
            return null;
        }

        if ($code === self::CODE) {
            return (float) $amount;
        }

        try {
            // Built here so that a missing converter can never block saving a record.
            return $this->injectableFactory->create(Converter::class)
                ->convert(Currency::create((float) $amount, $code), self::CODE)
                ->getAmount();
        } catch (Throwable) {
            return null;
        }
    }
}
