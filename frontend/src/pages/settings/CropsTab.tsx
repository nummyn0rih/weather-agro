import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type Crop,
  type CropCreate,
  type CropUpdate,
  createCrop,
  deleteCrop,
  listCrops,
  updateCrop,
} from '@/lib/crops-api';

import { EmptyBox, ErrorBox, FormSkeleton, getErrorMessage } from './shared';

interface CropForm {
  name: string;
  base_temperature: string;
  optimal_temp_min: string;
  optimal_temp_max: string;
}

const EMPTY_FORM: CropForm = {
  name: '',
  base_temperature: '',
  optimal_temp_min: '',
  optimal_temp_max: '',
};

function toForm(c: Crop): CropForm {
  return {
    name: c.name,
    base_temperature: String(c.base_temperature),
    optimal_temp_min: c.optimal_temp_min === null ? '' : String(c.optimal_temp_min),
    optimal_temp_max: c.optimal_temp_max === null ? '' : String(c.optimal_temp_max),
  };
}

function parseNullableNumber(v: string): number | null {
  if (v.trim() === '') return null;
  const n = Number.parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

export function CropsTab() {
  const queryClient = useQueryClient();
  const cropsQuery = useQuery({
    queryKey: ['crops'],
    queryFn: listCrops,
  });

  const [editing, setEditing] = useState<{
    mode: 'create' | 'edit';
    crop: Crop | null;
    form: CropForm;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Crop | null>(null);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['crops'] });

  const createMutation = useMutation({
    mutationFn: (input: CropCreate) => createCrop(input),
    onSuccess: () => {
      toast.success('Культура создана');
      setEditing(null);
      void invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: (vars: { id: number; input: CropUpdate }) =>
      updateCrop(vars.id, vars.input),
    onSuccess: () => {
      toast.success('Сохранено');
      setEditing(null);
      void invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteCrop(id),
    onSuccess: () => {
      toast.success('Удалено');
      setDeleteTarget(null);
      void invalidate();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
      setDeleteTarget(null);
    },
  });

  if (cropsQuery.isPending) return <FormSkeleton rows={4} />;
  if (cropsQuery.isError)
    return <ErrorBox message={getErrorMessage(cropsQuery.error)} />;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    const { form, mode, crop } = editing;
    if (form.name.trim() === '') {
      toast.error('Укажите название');
      return;
    }
    const base = Number.parseFloat(form.base_temperature);
    if (!Number.isFinite(base)) {
      toast.error('Базовая температура должна быть числом');
      return;
    }
    const payload: CropCreate = {
      name: form.name.trim(),
      base_temperature: base,
      optimal_temp_min: parseNullableNumber(form.optimal_temp_min),
      optimal_temp_max: parseNullableNumber(form.optimal_temp_max),
    };
    if (mode === 'create') {
      createMutation.mutate(payload);
    } else if (crop) {
      updateMutation.mutate({ id: crop.id, input: payload });
    }
  };

  const data = cropsQuery.data;
  const isMutating = createMutation.isPending || updateMutation.isPending;

  const inputClass =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text placeholder:text-notion-text-subtle focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const numInputClass = `notion-numeric font-mono ${inputClass}`;
  const labelClass =
    'text-[11px] font-medium uppercase tracking-wide text-notion-text-muted';
  const outlineBtn =
    'rounded-notion-sm border-notion-border bg-notion-bg text-notion-text transition-colors hover:bg-notion-row-hover focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const primaryBtn =
    'rounded-notion-sm bg-notion-accent-blue text-white transition-colors hover:bg-notion-accent-blue/90 focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const ghostIconBtn =
    'h-7 w-7 rounded-notion-sm text-notion-text-muted transition-colors hover:bg-notion-row-hover hover:text-notion-text focus-visible:ring-1 focus-visible:ring-notion-accent-blue focus-visible:ring-offset-0';
  const dialogContentClass =
    'rounded-notion-md border-notion-border bg-notion-bg text-notion-text shadow-notion-md';
  const dialogTitleClass = 'text-notion-text';
  const dialogDescClass = 'text-notion-text-muted';

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() =>
            setEditing({ mode: 'create', crop: null, form: EMPTY_FORM })
          }
          className={primaryBtn}
        >
          <Plus className="mr-2 h-4 w-4" />
          Добавить культуру
        </Button>
      </div>

      {data.length === 0 ? (
        <EmptyBox message="Культуры ещё не добавлены." />
      ) : (
        <div className="overflow-hidden overflow-x-auto rounded-notion-md border border-notion-border bg-notion-bg">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-notion-bg-secondary">
              <TableRow className="border-notion-border hover:bg-transparent">
                <TableHead className="text-[11px] font-medium uppercase tracking-wide text-notion-text-muted">
                  Название
                </TableHead>
                <TableHead className="text-right text-[11px] font-medium uppercase tracking-wide text-notion-text-muted">
                  Базовая T° (GDD)
                </TableHead>
                <TableHead className="text-right text-[11px] font-medium uppercase tracking-wide text-notion-text-muted">
                  Опт. мин.
                </TableHead>
                <TableHead className="text-right text-[11px] font-medium uppercase tracking-wide text-notion-text-muted">
                  Опт. макс.
                </TableHead>
                <TableHead className="w-[110px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((crop) => (
                <TableRow
                  key={crop.id}
                  className="border-notion-border transition-colors hover:bg-notion-row-hover"
                >
                  <TableCell className="font-medium text-notion-text">
                    {crop.name}
                  </TableCell>
                  <TableCell className="notion-numeric text-right font-mono text-notion-text">
                    {crop.base_temperature}
                  </TableCell>
                  <TableCell className="notion-numeric text-right font-mono text-notion-text">
                    {crop.optimal_temp_min ?? '—'}
                  </TableCell>
                  <TableCell className="notion-numeric text-right font-mono text-notion-text">
                    {crop.optimal_temp_max ?? '—'}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Редактировать"
                        onClick={() =>
                          setEditing({
                            mode: 'edit',
                            crop,
                            form: toForm(crop),
                          })
                        }
                        className={ghostIconBtn}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Удалить"
                        onClick={() => setDeleteTarget(crop)}
                        className={ghostIconBtn}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
      >
        <DialogContent className={dialogContentClass}>
          <DialogHeader>
            <DialogTitle className={dialogTitleClass}>
              {editing?.mode === 'edit'
                ? `Редактировать «${editing.crop?.name ?? ''}»`
                : 'Новая культура'}
            </DialogTitle>
            <DialogDescription className={dialogDescClass}>
              Базовая температура используется для расчёта GDD.
            </DialogDescription>
          </DialogHeader>
          {editing && (
            <form id="crop-form" onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="crop-name" className={labelClass}>
                  Название
                </Label>
                <Input
                  id="crop-name"
                  value={editing.form.name}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      form: { ...editing.form, name: e.target.value },
                    })
                  }
                  required
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="crop-base" className={labelClass}>
                  Базовая T° (°C)
                </Label>
                <Input
                  id="crop-base"
                  type="number"
                  step="0.1"
                  value={editing.form.base_temperature}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      form: {
                        ...editing.form,
                        base_temperature: e.target.value,
                      },
                    })
                  }
                  required
                  className={numInputClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="crop-min" className={labelClass}>
                    Опт. мин. (°C)
                  </Label>
                  <Input
                    id="crop-min"
                    type="number"
                    step="0.1"
                    value={editing.form.optimal_temp_min}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        form: {
                          ...editing.form,
                          optimal_temp_min: e.target.value,
                        },
                      })
                    }
                    className={numInputClass}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="crop-max" className={labelClass}>
                    Опт. макс. (°C)
                  </Label>
                  <Input
                    id="crop-max"
                    type="number"
                    step="0.1"
                    value={editing.form.optimal_temp_max}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        form: {
                          ...editing.form,
                          optimal_temp_max: e.target.value,
                        },
                      })
                    }
                    className={numInputClass}
                  />
                </div>
              </div>
            </form>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditing(null)}
              disabled={isMutating}
              className={outlineBtn}
            >
              Отмена
            </Button>
            <Button
              form="crop-form"
              type="submit"
              disabled={isMutating}
              className={primaryBtn}
            >
              {isMutating ? 'Сохранение…' : 'Сохранить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent className={dialogContentClass}>
          <AlertDialogHeader>
            <AlertDialogTitle className={dialogTitleClass}>
              Удалить культуру?
            </AlertDialogTitle>
            <AlertDialogDescription className={dialogDescClass}>
              {deleteTarget
                ? `Культура «${deleteTarget.name}» будет удалена. Если на неё ссылаются события или локации — backend вернёт 409.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={deleteMutation.isPending}
              className={outlineBtn}
            >
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
              }}
              disabled={deleteMutation.isPending}
              className="rounded-notion-sm bg-[var(--notion-chip-red-fg)] text-white transition-colors hover:bg-[var(--notion-chip-red-fg)]/90"
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default CropsTab;
